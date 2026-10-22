"""PostgreSQL canonical snapshot capture for reconciliation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.execution.adapters.postgres.models import FillModel
from pytradekit.orders.adapters.postgres.models import OrderModel
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.adapters.postgres.models import BalanceModel, PositionModel
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    CanonicalBalance,
    CanonicalFill,
    CanonicalOrder,
    CanonicalPosition,
    ExternalActivityOrigin,
    InternalSnapshot,
    ReconciliationScope,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.reconciliation.ports import InternalSnapshotPort
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import Currency, InstrumentId


class PostgresInternalSnapshotPort(InternalSnapshotPort):
    """Capture a consistent single-account view from durable canonical tables."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        clock: ClockPort,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot:
        captured_at = self._clock.now()
        with self._session_factory() as session:
            orders = tuple(
                session.execute(
                    select(OrderModel).order_by(OrderModel.created_at, OrderModel.id)
                )
                .scalars()
                .all()
            )
            fills = tuple(
                session.execute(
                    select(FillModel).order_by(FillModel.occurred_at, FillModel.id)
                )
                .scalars()
                .all()
            )
            positions = tuple(
                session.execute(
                    select(PositionModel)
                    .where(PositionModel.account_id == account_id.value)
                    .order_by(PositionModel.instrument_id)
                )
                .scalars()
                .all()
            )
            balances = tuple(
                session.execute(
                    select(BalanceModel)
                    .where(BalanceModel.account_id == account_id.value)
                    .order_by(BalanceModel.currency)
                )
                .scalars()
                .all()
            )

        order_by_id = {row.id: row for row in orders}
        completeness = SnapshotCompleteness.COMPLETE
        canonical_fills: list[CanonicalFill] = []
        if scope in {ReconciliationScope.FILLS, ReconciliationScope.FULL}:
            for row in fills:
                external_fill_id = (
                    row.external_fill_id.strip()
                    if row.external_fill_id is not None
                    else ""
                )
                if not external_fill_id:
                    completeness = SnapshotCompleteness.PARTIAL
                    continue
                order = order_by_id.get(row.order_id)
                canonical_fills.append(
                    CanonicalFill(
                        external_fill_id=external_fill_id,
                        order_id=OrderId(row.order_id),
                        external_order_id=(
                            order.external_order_id
                            if order is not None
                            else None
                        ),
                        quantity=row.quantity,
                        price=row.price_value,
                        currency=Currency(row.price_currency),
                        occurred_at=row.occurred_at,
                        origin=ExternalActivityOrigin.INTERNAL,
                    )
                )

        canonical_orders = (
            tuple(
                CanonicalOrder(
                    order_id=OrderId(row.id),
                    client_order_id=row.client_order_id,
                    external_order_id=row.external_order_id,
                    status=row.status,
                    filled_quantity=row.filled_quantity,
                    cancel_requested=row.cancel_requested,
                )
                for row in orders
            )
            if scope in {ReconciliationScope.ORDERS, ReconciliationScope.FULL}
            else ()
        )
        canonical_positions = (
            tuple(
                CanonicalPosition(
                    instrument_id=InstrumentId(row.instrument_id),
                    quantity=row.quantity,
                    average_price=row.average_price,
                    currency=Currency(row.currency),
                )
                for row in positions
            )
            if scope in {ReconciliationScope.POSITIONS, ReconciliationScope.FULL}
            else ()
        )
        canonical_balances = (
            tuple(
                CanonicalBalance(
                    currency=Currency(row.currency),
                    cash=row.cash,
                )
                for row in balances
            )
            if scope
            in {
                ReconciliationScope.ACCOUNT,
                ReconciliationScope.BALANCES,
                ReconciliationScope.FULL,
            }
            else ()
        )

        version = (
            len(orders)
            + sum(row.version for row in orders)
            + len(fills)
            + len(positions)
            + sum(row.version for row in positions)
            + len(balances)
            + sum(row.version for row in balances)
        )
        watermark = SnapshotWatermark(
            captured_at=captured_at,
            internal_version=version,
        )
        return InternalSnapshot(
            account_id=account_id,
            orders=canonical_orders,
            fills=tuple(canonical_fills),
            positions=canonical_positions,
            balances=canonical_balances,
            captured_at=captured_at,
            watermark=watermark,
            completeness=completeness,
        )


class PostgresOrderIdentityResolver:
    """Resolve provider order identity back to the canonical OrderId."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def resolve_order_id(
        self,
        external_order_id: str,
        client_order_id: str | None = None,
    ) -> OrderId | None:
        external = external_order_id.strip()
        client = client_order_id.strip() if client_order_id is not None else ""
        with self._session_factory() as session:
            row = None
            if external:
                row = session.execute(
                    select(OrderModel).where(
                        OrderModel.external_order_id == external
                    )
                ).scalar_one_or_none()
            if row is None and client:
                row = session.execute(
                    select(OrderModel).where(
                        OrderModel.client_order_id == client
                    )
                ).scalar_one_or_none()
        return OrderId(row.id) if row is not None else None
