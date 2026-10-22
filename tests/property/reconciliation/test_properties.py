"""LOT-02 reconciliation safety properties."""

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.reconciliation import (
    BrokerSnapshot,
    InternalSnapshot,
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
    ReconciliationScope,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.services import ConvergenceService, SnapshotComparator


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


@given(
    st.sampled_from(
        [
            SnapshotCompleteness.PARTIAL,
            SnapshotCompleteness.UNKNOWN,
        ]
    )
)
def test_incomplete_broker_evidence_never_produces_high_confidence(
    completeness: SnapshotCompleteness,
) -> None:
    result = ConvergenceService().evaluate(
        internal_completeness=SnapshotCompleteness.COMPLETE,
        broker_completeness=completeness,
        mismatches=(),
    )

    assert result.confidence.value != "HIGH"


@given(st.sampled_from(list(ReconciliationScope)))
def test_same_snapshots_produce_same_mismatches(
    scope: ReconciliationScope,
) -> None:
    now = datetime(2026, 10, 22, 13, tzinfo=UTC)
    account_id = AccountId.new()
    run_id = ReconciliationRunId.new()
    internal = InternalSnapshot(
        account_id=account_id,
        orders=(),
        fills=(),
        positions=(),
        balances=(),
        captured_at=now,
        watermark=SnapshotWatermark(captured_at=now, internal_version=1),
        completeness=SnapshotCompleteness.COMPLETE,
    )
    broker = BrokerSnapshot(
        account_id=account_id,
        provider="property",
        orders=(),
        fills=(),
        positions=(),
        balances=(),
        captured_at=now,
        watermark=SnapshotWatermark(captured_at=now, provider_as_of=now),
        completeness=SnapshotCompleteness.PARTIAL,
    )
    comparator = SnapshotComparator()

    first = comparator.compare(
        run_id=run_id,
        scope=scope,
        internal=internal,
        broker=broker,
        detected_at=now,
    )
    second = comparator.compare(
        run_id=run_id,
        scope=scope,
        internal=internal,
        broker=broker,
        detected_at=now,
    )

    assert first == second
