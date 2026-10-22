"""Explicit policy for planning mismatch resolutions."""

from pytradekit.reconciliation.domain import (
    Mismatch,
    MismatchType,
    Resolution,
    ResolutionId,
    ResolutionType,
)
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import CorrelationId


class ResolveMismatch:
    """Turn one mismatch into an explicit auditable resolution plan."""

    def __init__(self, *, clock: ClockPort) -> None:
        self._clock = clock

    def plan(self, mismatch: Mismatch, *, correlation_id: CorrelationId) -> Resolution:
        resolution_type, reason = _resolution_policy(mismatch.type)
        return Resolution(
            id=ResolutionId.new(),
            run_id=mismatch.run_id,
            mismatch_id=mismatch.id,
            type=resolution_type,
            reason=reason,
            actor="system",
            started_at=self._clock.now(),
            correlation_id=correlation_id,
        )


def _resolution_policy(mismatch_type: MismatchType) -> tuple[ResolutionType, str]:
    if mismatch_type is MismatchType.MISSING_INTERNAL_FILL:
        return (
            ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT,
            "Import the proven provider execution through the canonical fill path.",
        )
    if mismatch_type in {
        MismatchType.UNKNOWN_EXTERNAL_ORDER,
        MismatchType.UNKNOWN_EXTERNAL_FILL,
        MismatchType.UNKNOWN_EXTERNAL_ACTIVITY,
    }:
        return (
            ResolutionType.IMPORT_EXTERNAL_ACTIVITY,
            "Preserve proven external activity explicitly before convergence.",
        )
    if mismatch_type in {
        MismatchType.SNAPSHOT_INCOMPLETE,
        MismatchType.SNAPSHOT_UNAVAILABLE,
        MismatchType.STALE_RECONCILIATION,
    }:
        return (
            ResolutionType.REFRESH_SNAPSHOT,
            "Fresh evidence is required before any economic correction.",
        )
    if mismatch_type in {
        MismatchType.POSITION_QUANTITY_MISMATCH,
        MismatchType.POSITION_MISSING_INTERNAL,
        MismatchType.POSITION_MISSING_EXTERNAL,
        MismatchType.BALANCE_MISMATCH,
    }:
        return (
            ResolutionType.MANUAL_REVIEW,
            "Causality must be established before rebuilding derived economic state.",
        )
    if mismatch_type in {
        MismatchType.ORDER_STATUS_MISMATCH,
        MismatchType.ORDER_FILLED_QUANTITY_MISMATCH,
        MismatchType.ORDER_IDENTITY_MISMATCH,
        MismatchType.FILL_VALUE_MISMATCH,
    }:
        return (
            ResolutionType.MANUAL_REVIEW,
            "Conflicting economic facts require explicit review.",
        )
    return (
        ResolutionType.BLOCK_TRADING,
        "No safe automatic resolution is justified by current evidence.",
    )
