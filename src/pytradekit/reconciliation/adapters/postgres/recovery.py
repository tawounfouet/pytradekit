"""Evidence-backed PostgreSQL recovery resolution executor."""

from __future__ import annotations

from collections.abc import Callable

from pytradekit.execution import Fill, FillId
from pytradekit.orders.application import ProcessFill
from pytradekit.persistence.events import OutboxRecord
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.adapters import OrdersPortfolioEffectAdapter
from pytradekit.portfolio.application import ApplyFillToPortfolio
from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    CanonicalFill,
    Mismatch,
    Resolution,
    ResolutionType,
)
from pytradekit.reconciliation.ports import ResolutionExecutorPort
from pytradekit.shared import Price, Quantity


class RecoveryEvidenceError(RuntimeError):
    """Raised when an economic correction is not justified by stable evidence."""


class PostgresResolutionExecutor(ResolutionExecutorPort):
    """Import proven fills through the normal OMS and Portfolio path."""

    def __init__(
        self,
        uow_factory: Callable[[], PostgresUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def supports(self, resolution_type: ResolutionType) -> bool:
        return resolution_type in {
            ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT,
            ResolutionType.IMPORT_EXTERNAL_ACTIVITY,
        }

    def apply(
        self,
        *,
        resolution: Resolution,
        mismatch: Mismatch,
        broker_snapshot: BrokerSnapshot,
    ) -> None:
        if resolution.type not in {
            ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT,
            ResolutionType.IMPORT_EXTERNAL_ACTIVITY,
        }:
            raise RecoveryEvidenceError(
                f"Resolution type {resolution.type.value} is not a fill import."
            )
        if mismatch.entity_type != "fill" or mismatch.entity_id is None:
            raise RecoveryEvidenceError(
                "Automatic external activity import is limited to proven fill facts."
            )

        canonical = _find_fill(broker_snapshot, mismatch.entity_id)
        with self._uow_factory() as uow:
            order = None
            if canonical.order_id is not None:
                order = uow.orders.get(canonical.order_id)
            if order is None and canonical.external_order_id is not None:
                order = uow.orders.get_by_external_order_id(canonical.external_order_id)
            if order is None:
                raise RecoveryEvidenceError(
                    "Provider fill cannot be linked to a canonical order."
                )

            existing = next(
                (
                    item
                    for item in uow.fills.list_for_order(order.id)
                    if item.external_fill_id == canonical.external_fill_id
                ),
                None,
            )
            fill = existing or Fill(
                id=FillId.new(),
                order_id=order.id,
                quantity=Quantity(canonical.quantity),
                price=Price(canonical.price, canonical.currency),
                occurred_at=canonical.occurred_at,
                external_fill_id=canonical.external_fill_id,
            )
            if existing is None:
                uow.fills.add(fill)

            effects = OrdersPortfolioEffectAdapter(
                ApplyFillToPortfolio(
                    positions=uow.positions,
                    balances=uow.balances,
                    processed_fills=uow.processed_fills,
                )
            )
            ProcessFill(
                repository=uow.orders,
                portfolio_effects=effects,
            ).execute(
                fill,
                external_order_id=canonical.external_order_id,
                account_id=broker_snapshot.account_id,
            )
            uow.outbox.add(
                OutboxRecord.create(
                    event_type="ExternalFillImported",
                    aggregate_type="Fill",
                    aggregate_id=str(fill.id),
                    payload={
                        "fill_id": str(fill.id),
                        "external_fill_id": canonical.external_fill_id,
                        "order_id": str(order.id),
                        "origin": canonical.origin.value,
                    },
                    occurred_at=canonical.occurred_at,
                    correlation_id=str(resolution.correlation_id),
                )
            )
            uow.commit()


def _find_fill(snapshot: BrokerSnapshot, external_fill_id: str) -> CanonicalFill:
    for fill in snapshot.fills:
        if fill.external_fill_id == external_fill_id:
            return fill
    raise RecoveryEvidenceError(
        f"Broker snapshot does not contain fill {external_fill_id}."
    )
