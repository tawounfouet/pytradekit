"""Generic 0.6 reconciliation gate tests for Alpaca PAPER."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy.orm import Session

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
    ReconciliationOutcome,
    ReconciliationServicePort,
    RecoveryWorkflowCoordinator,
)
from pytradekit.brokers.adapters.alpaca.generic_reconciliation import (
    AlpacaGenericReconciliationRuntime,
)
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    TradingReadinessReport,
)
from pytradekit.shared import CorrelationId

NOW = datetime(2026, 10, 22, 16, tzinfo=UTC)


class RecordingService:
    """Deterministic reconciliation service used by the runtime gate tests."""

    def __init__(
        self,
        *,
        status: ConsistencyStatus,
        confidence: StateConfidence,
        fail: bool = False,
    ) -> None:
        self._status = status
        self._confidence = confidence
        self._fail = fail
        self.calls = 0

    def execute(
        self,
        *,
        account_id: AccountId,
        trigger: ReconciliationTrigger,
        correlation_id: CorrelationId,
        scope: ReconciliationScope = ReconciliationScope.FULL,
    ) -> ReconciliationOutcome:
        self.calls += 1
        if self._fail:
            raise RuntimeError("synthetic reconciliation failure")

        run = ReconciliationRun.create(
            account_id=account_id,
            scope=scope,
            trigger=trigger,
            started_at=NOW,
            correlation_id=correlation_id,
        )
        run.transition_to(ReconciliationRunStatus.CAPTURING)
        run.transition_to(ReconciliationRunStatus.COMPARING)
        run.complete(
            completed_at=NOW,
            result_status=self._status,
            confidence=self._confidence,
            mismatch_count=0,
            critical_mismatch_count=0,
        )
        return ReconciliationOutcome(
            run=run,
            mismatches=(),
            resolutions=(),
        )


def _base_report(*, ready: bool = True) -> TradingReadinessReport:
    return TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(
            ReadinessCheck(
                name="baseline",
                status=(
                    ReadinessCheckStatus.PASS
                    if ready
                    else ReadinessCheckStatus.FAIL
                ),
                detail="qualified 0.5 startup baseline",
            ),
        ),
        gaps=() if ready else ("baseline failed",),
    )


def _runtime(service: RecordingService) -> AlpacaGenericReconciliationRuntime:
    registry = ConsistencyRegistry()
    workflows = RecoveryWorkflowCoordinator(
        reconciliation=cast(ReconciliationServicePort, service)
    )
    return AlpacaGenericReconciliationRuntime(
        account_id=AccountId.new(),
        workflows=workflows,
        consistency_gate=ConsistencyAdmissionPolicy(registry),
        registry=registry,
        session=cast(Session, object()),
    )


def test_startup_gate_preserves_ready_only_for_consistent_high() -> None:
    service = RecordingService(
        status=ConsistencyStatus.CONSISTENT,
        confidence=StateConfidence.HIGH,
    )

    report = _runtime(service).startup(_base_report())

    assert service.calls == 1
    assert report.trading_ready
    assert report.consistency_status is ConsistencyStatus.CONSISTENT
    assert report.state_confidence is StateConfidence.HIGH
    assert report.checks[-1].name == "generic_reconciliation"
    assert report.checks[-1].status is ReadinessCheckStatus.PASS


def test_startup_gate_blocks_degraded_or_low_confidence_state() -> None:
    service = RecordingService(
        status=ConsistencyStatus.DEGRADED,
        confidence=StateConfidence.MEDIUM,
    )

    report = _runtime(service).startup(_base_report())

    assert not report.trading_ready
    assert report.consistency_status is ConsistencyStatus.DEGRADED
    assert report.state_confidence is StateConfidence.MEDIUM
    assert "generic reconciliation did not prove CONSISTENT/HIGH" in report.gaps


def test_startup_gate_fails_closed_when_reconciliation_raises() -> None:
    service = RecordingService(
        status=ConsistencyStatus.UNKNOWN,
        confidence=StateConfidence.UNKNOWN,
        fail=True,
    )

    report = _runtime(service).startup(_base_report())

    assert service.calls == 1
    assert not report.trading_ready
    assert report.checks[-1].status is ReadinessCheckStatus.FAIL
    assert report.consistency_status is None
    assert report.state_confidence is None


def test_startup_gate_does_not_run_when_baseline_is_already_not_ready() -> None:
    service = RecordingService(
        status=ConsistencyStatus.CONSISTENT,
        confidence=StateConfidence.HIGH,
    )
    baseline = _base_report(ready=False)

    report = _runtime(service).startup(baseline)

    assert report is baseline
    assert service.calls == 0
