"""Deterministic canonical order comparison."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pytradekit.reconciliation.domain import (
    CanonicalOrder,
    Mismatch,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
)

from ._support import mismatch, sort_mismatches


class OrderComparator:
    """Compare canonical internal and broker order facts."""

    def compare(
        self,
        *,
        run_id: ReconciliationRunId,
        internal: tuple[CanonicalOrder, ...],
        external: tuple[CanonicalOrder, ...],
        detected_at: datetime,
    ) -> tuple[Mismatch, ...]:
        """Return deterministic order mismatches."""

        remaining = list(external)
        result: list[Mismatch] = []

        for local in sorted(internal, key=_sort_key):
            remote_index = _matching_index(local, remaining)
            if remote_index is None:
                result.append(
                    mismatch(
                        run_id=run_id,
                        mismatch_type=MismatchType.MISSING_EXTERNAL_ORDER,
                        severity=MismatchSeverity.HIGH,
                        entity_type="order",
                        entity_id=_entity_id(local),
                        internal_value=_evidence(local),
                        external_value=None,
                        detected_at=detected_at,
                    )
                )
                continue

            remote = remaining.pop(remote_index)
            entity_id = _entity_id(local)

            if (
                local.external_order_id is not None
                and remote.external_order_id is not None
                and local.external_order_id != remote.external_order_id
            ):
                result.append(
                    mismatch(
                        run_id=run_id,
                        mismatch_type=MismatchType.ORDER_IDENTITY_MISMATCH,
                        severity=MismatchSeverity.CRITICAL,
                        entity_type="order",
                        entity_id=entity_id,
                        internal_value=_evidence(local),
                        external_value=_evidence(remote),
                        detected_at=detected_at,
                    )
                )

            if local.status != remote.status:
                result.append(
                    mismatch(
                        run_id=run_id,
                        mismatch_type=MismatchType.ORDER_STATUS_MISMATCH,
                        severity=MismatchSeverity.HIGH,
                        entity_type="order",
                        entity_id=entity_id,
                        internal_value={"status": local.status},
                        external_value={"status": remote.status},
                        detected_at=detected_at,
                    )
                )

            if local.filled_quantity != remote.filled_quantity:
                result.append(
                    mismatch(
                        run_id=run_id,
                        mismatch_type=MismatchType.ORDER_FILLED_QUANTITY_MISMATCH,
                        severity=MismatchSeverity.CRITICAL,
                        entity_type="order",
                        entity_id=entity_id,
                        internal_value={"filled_quantity": str(local.filled_quantity)},
                        external_value={"filled_quantity": str(remote.filled_quantity)},
                        detected_at=detected_at,
                    )
                )

        for remote in sorted(remaining, key=_sort_key):
            mismatch_type = (
                MismatchType.UNKNOWN_EXTERNAL_ORDER
                if remote.order_id is None
                else MismatchType.MISSING_INTERNAL_ORDER
            )
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=mismatch_type,
                    severity=MismatchSeverity.CRITICAL,
                    entity_type="order",
                    entity_id=_entity_id(remote),
                    internal_value=None,
                    external_value=_evidence(remote),
                    detected_at=detected_at,
                )
            )

        return sort_mismatches(result)


def _matching_index(
    local: CanonicalOrder,
    candidates: list[CanonicalOrder],
) -> int | None:
    local_tokens = _identity_tokens(local)
    for index, candidate in enumerate(candidates):
        if local_tokens.intersection(_identity_tokens(candidate)):
            return index
    return None


def _identity_tokens(order: CanonicalOrder) -> set[str]:
    tokens: set[str] = set()
    if order.order_id is not None:
        tokens.add(f"order:{order.order_id}")
    if order.client_order_id is not None:
        tokens.add(f"client:{order.client_order_id}")
    if order.external_order_id is not None:
        tokens.add(f"external:{order.external_order_id}")
    return tokens


def _entity_id(order: CanonicalOrder) -> str:
    if order.order_id is not None:
        return str(order.order_id)
    if order.external_order_id is not None:
        return order.external_order_id
    if order.client_order_id is not None:
        return order.client_order_id
    raise AssertionError("CanonicalOrder invariants require an identity.")


def _sort_key(order: CanonicalOrder) -> tuple[str, str, str]:
    return (
        str(order.order_id) if order.order_id is not None else "",
        order.client_order_id or "",
        order.external_order_id or "",
    )


def _evidence(order: CanonicalOrder) -> dict[str, str | bool]:
    return {
        "order_id": str(order.order_id) if order.order_id is not None else "",
        "client_order_id": order.client_order_id or "",
        "external_order_id": order.external_order_id or "",
        "status": order.status,
        "filled_quantity": str(order.filled_quantity),
        "cancel_requested": order.cancel_requested,
    }
