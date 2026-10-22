"""Fresh verification safety for reconciliation resolutions."""

from datetime import UTC, datetime, timedelta

from pytradekit.reconciliation import (
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
    Resolution,
    ResolutionId,
    ResolutionStatus,
    ResolutionType,
)
from pytradekit.reconciliation.application.reconcile_account import ReconcileAccount
from pytradekit.shared import CorrelationId
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 16, tzinfo=UTC)


class ResolutionRepository:
    def __init__(self) -> None:
        self.saved: list[Resolution] = []

    def save_resolution(self, resolution: Resolution) -> None:
        self.saved.append(resolution)

    def checkpoint(self) -> None:
        return None


def _applied_resolution() -> tuple[Mismatch, Resolution]:
    run_id = ReconciliationRunId.new()
    mismatch = Mismatch(
        id=MismatchId.new(),
        run_id=run_id,
        type=MismatchType.MISSING_INTERNAL_FILL,
        severity=MismatchSeverity.CRITICAL,
        entity_type="fill",
        entity_id="fill-1",
        internal_value=None,
        external_value={"external_fill_id": "fill-1"},
        detected_at=NOW,
    )
    resolution = Resolution(
        id=ResolutionId.new(),
        run_id=run_id,
        mismatch_id=mismatch.id,
        type=ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT,
        reason="proven fill",
        actor="system",
        started_at=NOW,
        correlation_id=CorrelationId.new(),
    )
    resolution.mark_applying()
    resolution.mark_applied(completed_at=NOW)
    return mismatch, resolution


def test_applied_resolution_requires_strictly_newer_verification_evidence() -> None:
    mismatch, resolution = _applied_resolution()
    repository = ResolutionRepository()
    service = object.__new__(ReconcileAccount)
    service._repository = repository
    service._clock = FakeClock(NOW + timedelta(seconds=1))

    service._verify_applied(
        (resolution,),
        (mismatch,),
        (),
        verification_cut=NOW,
    )

    assert resolution.status is ResolutionStatus.FAILED
    assert resolution.verification_status == "verification_not_fresh"


def test_newer_verification_can_mark_applied_resolution_verified() -> None:
    mismatch, resolution = _applied_resolution()
    repository = ResolutionRepository()
    service = object.__new__(ReconcileAccount)
    service._repository = repository
    service._clock = FakeClock(NOW + timedelta(seconds=2))

    service._verify_applied(
        (resolution,),
        (mismatch,),
        (),
        verification_cut=NOW + timedelta(seconds=1),
    )

    assert resolution.status is ResolutionStatus.VERIFIED
    assert resolution.verification_status == "fresh_evidence_converged"
