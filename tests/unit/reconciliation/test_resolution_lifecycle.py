"""Resolution lifecycle qualification for causal recovery."""

from datetime import UTC, datetime, timedelta

from pytradekit.reconciliation import (
    MismatchId,
    ReconciliationRunId,
    Resolution,
    ResolutionId,
    ResolutionStatus,
    ResolutionType,
)
from pytradekit.shared import CorrelationId

NOW = datetime(2026, 10, 22, 18, tzinfo=UTC)


def _planned() -> Resolution:
    return Resolution(
        id=ResolutionId.new(),
        run_id=ReconciliationRunId.new(),
        mismatch_id=MismatchId.new(),
        type=ResolutionType.MANUAL_REVIEW,
        reason="Causality must be established.",
        actor="system",
        started_at=NOW,
        correlation_id=CorrelationId.new(),
    )


def test_planned_resolution_can_close_without_claiming_application() -> None:
    resolution = _planned()

    resolution.mark_rejected(
        completed_at=NOW + timedelta(seconds=1),
        verification_status="superseded_by_fresh_convergence",
    )

    assert resolution.status is ResolutionStatus.REJECTED
    assert resolution.verification_status == "superseded_by_fresh_convergence"
    assert resolution.completed_at == NOW + timedelta(seconds=1)
