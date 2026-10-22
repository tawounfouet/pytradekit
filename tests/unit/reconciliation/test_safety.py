"""LOT-07 consistency and confidence admission safety."""

from datetime import UTC, datetime

import pytest

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    StateConfidence,
)
from pytradekit.reconciliation.application import (
    ConsistencyAdmissionPolicy,
    ConsistencyRegistry,
    UnsafeConsistencyError,
)
from pytradekit.shared import CorrelationId


def _completed(
    *,
    status: ConsistencyStatus,
    confidence: StateConfidence,
) -> ReconciliationRun:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    run = ReconciliationRun.create(
        account_id=AccountId.new(),
        scope=ReconciliationScope.FULL,
        trigger=ReconciliationTrigger.STARTUP,
        started_at=now,
        correlation_id=CorrelationId.new(),
    )
    run.transition_to(ReconciliationRunStatus.CAPTURING)
    run.transition_to(ReconciliationRunStatus.COMPARING)
    run.complete(
        completed_at=now,
        result_status=status,
        confidence=confidence,
        mismatch_count=0,
        critical_mismatch_count=0,
    )
    return run


def test_consistent_high_allows_risk_increase() -> None:
    run = _completed(
        status=ConsistencyStatus.CONSISTENT,
        confidence=StateConfidence.HIGH,
    )
    registry = ConsistencyRegistry()
    registry.record(run)

    ConsistencyAdmissionPolicy(registry).ensure_risk_increase_allowed(run.account_id)


@pytest.mark.parametrize(
    ("status", "confidence"),
    [
        (ConsistencyStatus.CONSISTENT, StateConfidence.MEDIUM),
        (ConsistencyStatus.DEGRADED, StateConfidence.MEDIUM),
        (ConsistencyStatus.INCONSISTENT, StateConfidence.LOW),
        (ConsistencyStatus.UNKNOWN, StateConfidence.UNKNOWN),
    ],
)
def test_unsafe_evidence_blocks_risk_increase(
    status: ConsistencyStatus,
    confidence: StateConfidence,
) -> None:
    run = _completed(status=status, confidence=confidence)
    registry = ConsistencyRegistry()
    registry.record(run)

    with pytest.raises(UnsafeConsistencyError):
        ConsistencyAdmissionPolicy(registry).ensure_risk_increase_allowed(
            run.account_id
        )


def test_clearing_safe_evidence_fail_closes_admission() -> None:
    run = _completed(
        status=ConsistencyStatus.CONSISTENT,
        confidence=StateConfidence.HIGH,
    )
    registry = ConsistencyRegistry()
    registry.record(run)
    policy = ConsistencyAdmissionPolicy(registry)
    policy.ensure_risk_increase_allowed(run.account_id)

    registry.clear(run.account_id)

    with pytest.raises(UnsafeConsistencyError):
        policy.ensure_risk_increase_allowed(run.account_id)
