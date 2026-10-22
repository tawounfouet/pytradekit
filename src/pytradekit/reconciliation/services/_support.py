"""Shared deterministic comparator helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from pytradekit.reconciliation.domain import (
    JsonEvidence,
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
)


def mismatch(
    *,
    run_id: ReconciliationRunId,
    mismatch_type: MismatchType,
    severity: MismatchSeverity,
    entity_type: str,
    entity_id: str | None,
    internal_value: JsonEvidence | None,
    external_value: JsonEvidence | None,
    detected_at: datetime,
) -> Mismatch:
    """Create a stable mismatch identity from deterministic evidence."""

    identity = "|".join(
        (
            str(run_id),
            mismatch_type.value,
            entity_type,
            entity_id or "",
        )
    )
    return Mismatch(
        id=MismatchId(uuid5(NAMESPACE_URL, identity)),
        run_id=run_id,
        type=mismatch_type,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        internal_value=internal_value,
        external_value=external_value,
        detected_at=detected_at,
    )


def sort_mismatches(values: list[Mismatch]) -> tuple[Mismatch, ...]:
    """Return mismatches in a stable provider-neutral order."""

    return tuple(
        sorted(
            values,
            key=lambda item: (
                item.type.value,
                item.entity_type,
                item.entity_id or "",
                str(item.id),
            ),
        )
    )
