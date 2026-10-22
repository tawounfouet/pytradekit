"""LOT-06 recovery workflow trigger semantics."""

from datetime import UTC, datetime
from typing import cast

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationScope,
    ReconciliationTrigger,
    RecoveryState,
    StateConfidence,
)
from pytradekit.reconciliation.application import (
    ReconciliationOutcome,
    ReconciliationServicePort,
    RecoveryWorkflowCoordinator,
)
from pytradekit.shared import CorrelationId


class RecordingReconciliation:
    def __init__(self) -> None:
        self.triggers: list[ReconciliationTrigger] = []

    def execute(
        self,
        *,
        account_id: AccountId,
        trigger: ReconciliationTrigger,
        correlation_id: CorrelationId,
        scope: ReconciliationScope = ReconciliationScope.FULL,
    ) -> ReconciliationOutcome:
        self.triggers.append(trigger)
        now = datetime(2026, 10, 22, 12, tzinfo=UTC)
        run = ReconciliationRun.create(
            account_id=account_id,
            scope=scope,
            trigger=trigger,
            started_at=now,
            correlation_id=correlation_id,
        )
        run.transition_to(run.status.CAPTURING)
        run.transition_to(run.status.COMPARING)
        run.complete(
            completed_at=now,
            result_status=ConsistencyStatus.CONSISTENT,
            confidence=StateConfidence.HIGH,
            mismatch_count=0,
            critical_mismatch_count=0,
        )
        return ReconciliationOutcome(run=run, mismatches=(), resolutions=())


def test_operational_triggers_use_the_same_reconciliation_service() -> None:
    service = RecordingReconciliation()
    workflows = RecoveryWorkflowCoordinator(
        reconciliation=cast(ReconciliationServicePort, service)
    )
    account_id = AccountId.new()

    workflows.startup(account_id=account_id, correlation_id=CorrelationId.new())
    workflows.reconnect(account_id=account_id, correlation_id=CorrelationId.new())
    workflows.submit_uncertainty(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )
    workflows.incident(account_id=account_id, correlation_id=CorrelationId.new())
    workflows.periodic(account_id=account_id, correlation_id=CorrelationId.new())

    assert service.triggers == [
        ReconciliationTrigger.STARTUP,
        ReconciliationTrigger.RECONNECT,
        ReconciliationTrigger.SUBMIT_UNCERTAINTY,
        ReconciliationTrigger.INCIDENT,
        ReconciliationTrigger.PERIODIC,
    ]
    assert workflows.state is RecoveryState.RECOVERED
