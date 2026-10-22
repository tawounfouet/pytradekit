"""LOT-02 reconciliation safety properties."""

from datetime import UTC, datetime

from hypothesis import given\nfrom hypothesis import strategies as st

from pytradekit.reconciliation import (
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
    SnapshotCompleteness,
)
from pytradekit.reconciliation.services import ConvergenceService


@given(st.sampled_from(list(MismatchType)))
def test_unresolved_critical_mismatch_never_produces_consistent(
    mismatch_type: MismatchType,
) -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    mismatch = Mismatch(
        id=MismatchId.new(),
        run_id=ReconciliationRunId.new(),
        type=mismatch_type,
        severity=MismatchSeverity.CRITICAL,
        entity_type="property",
        entity_id="x",
        internal_value=None,
        external_value=None,
        detected_at=now,
    )

    result = ConvergenceService().evaluate(
        internal_completeness=SnapshotCompleteness.COMPLETE,
        broker_completeness=SnapshotCompleteness.COMPLETE,
        mismatches=(mismatch,),
    )

    assert result.status.value != "CONSISTENT"


@given(st.sampled_from([SnapshotCompleteness.PARTIAL, SnapshotCompleteness.UNKNOWN]))
def test_incomplete_broker_evidence_never_produces_high_confidence(
    completeness: SnapshotCompleteness,
) -> None:
    result = ConvergenceService().evaluate(
        internal_completeness=SnapshotCompleteness.COMPLETE,
        broker_completeness=completeness,
        mismatches=(),
    )

    assert result.confidence.value != "HIGH"
