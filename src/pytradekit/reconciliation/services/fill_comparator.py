"""Deterministic canonical fill comparison."""

from __future__ import annotations

from datetime import datetime

from pytradekit.reconciliation.domain import (
    CanonicalFill,
    Mismatch,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
)

from ._support import mismatch, sort_mismatches


class FillComparator:
    """Compare immutable execution facts by stable external identity."""

    def compare(
        self,
        *,
        run_id: ReconciliationRunId,
        internal: tuple[CanonicalFill, ...],
        external: tuple[CanonicalFill, ...],
        detected_at: datetime,
    ) -> tuple[Mismatch, ...]:
        """Return deterministic fill mismatches."""

        internal_by_id = {item.external_fill_id: item for item in internal}
        external_by_id = {item.external_fill_id: item for item in external}
        result: list[Mismatch] = []

        for fill_id in sorted(internal_by_id.keys() - external_by_id.keys()):
            local = internal_by_id[fill_id]
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=MismatchType.MISSING_EXTERNAL_FILL,
                    severity=MismatchSeverity.HIGH,
                    entity_type="fill",
                    entity_id=fill_id,
                    internal_value=_evidence(local),
                    external_value=None,
                    detected_at=detected_at,
                )
            )

        for fill_id in sorted(external_by_id.keys() - internal_by_id.keys()):
            remote = external_by_id[fill_id]
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=(
                        MismatchType.MISSING_INTERNAL_FILL
                        if remote.order_id is not None
                        else MismatchType.UNKNOWN_EXTERNAL_FILL
                    ),
                    severity=MismatchSeverity.CRITICAL,
                    entity_type="fill",
                    entity_id=fill_id,
                    internal_value=None,
                    external_value=_evidence(remote),
                    detected_at=detected_at,
                )
            )

        for fill_id in sorted(internal_by_id.keys() & external_by_id.keys()):
            local = internal_by_id[fill_id]
            remote = external_by_id[fill_id]
            if (
                local.order_id != remote.order_id
                or local.external_order_id != remote.external_order_id
                or local.quantity != remote.quantity
                or local.price != remote.price
                or local.currency != remote.currency
                or local.occurred_at != remote.occurred_at
            ):
                result.append(
                    mismatch(
                        run_id=run_id,
                        mismatch_type=MismatchType.FILL_VALUE_MISMATCH,
                        severity=MismatchSeverity.CRITICAL,
                        entity_type="fill",
                        entity_id=fill_id,
                        internal_value=_evidence(local),
                        external_value=_evidence(remote),
                        detected_at=detected_at,
                    )
                )

        return sort_mismatches(result)


def _evidence(fill: CanonicalFill) -> dict[str, str]:
    return {
        "external_fill_id": fill.external_fill_id,
        "order_id": str(fill.order_id) if fill.order_id is not None else "",
        "external_order_id": fill.external_order_id or "",
        "quantity": str(fill.quantity),
        "price": str(fill.price),
        "currency": str(fill.currency),
        "occurred_at": fill.occurred_at.isoformat(),
        "origin": fill.origin.value,
    }
