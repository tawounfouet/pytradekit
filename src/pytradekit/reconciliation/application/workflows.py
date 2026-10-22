"""Operational recovery workflows using one generic reconciliation pipeline."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Protocol

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application.reconcile_account import ReconciliationOutcome
from pytradekit.reconciliation.application.stale_runs import StaleRunRecovery
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    RecoveryState,
    StateConfidence,
)
from pytradekit.shared import CorrelationId


class ReconciliationServicePort(Protocol):
    """Application surface required by recovery trigger orchestration."""

    def execute(
        self,
        *,
        account_id: AccountId,
        trigger: ReconciliationTrigger,
        correlation_id: CorrelationId,
        scope: ReconciliationScope = ReconciliationScope.FULL,
    ) -> ReconciliationOutcome: ...


class RecoveryWorkflowCoordinator:
    """Map every operational uncertainty trigger to ReconcileAccount."""

    def __init__(
        self,
        *,
        reconciliation: ReconciliationServicePort,
        stale_runs: StaleRunRecovery | None = None,
        containment: Callable[[AccountId], None] | None = None,
    ) -> None:
        self._reconciliation = reconciliation
        self._stale_runs = stale_runs
        self._containment = containment
        self._lock = Lock()
        self._state = RecoveryState.IDLE

    @property
    def state(self) -> RecoveryState:
        with self._lock:
            return self._state

    def startup(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._execute(
            account_id=account_id,
            correlation_id=correlation_id,
            trigger=ReconciliationTrigger.STARTUP,
        )

    def periodic(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._execute(
            account_id=account_id,
            correlation_id=correlation_id,
            trigger=ReconciliationTrigger.PERIODIC,
        )

    def reconnect(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._execute(
            account_id=account_id,
            correlation_id=correlation_id,
            trigger=ReconciliationTrigger.RECONNECT,
        )

    def submit_uncertainty(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._execute(
            account_id=account_id,
            correlation_id=correlation_id,
            trigger=ReconciliationTrigger.SUBMIT_UNCERTAINTY,
        )

    def incident(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._execute(
            account_id=account_id,
            correlation_id=correlation_id,
            trigger=ReconciliationTrigger.INCIDENT,
        )

    def manual(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
        scope: ReconciliationScope = ReconciliationScope.FULL,
    ) -> ReconciliationOutcome:
        return self._execute(
            account_id=account_id,
            correlation_id=correlation_id,
            trigger=ReconciliationTrigger.MANUAL,
            scope=scope,
        )

    def _execute(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
        trigger: ReconciliationTrigger,
        scope: ReconciliationScope = ReconciliationScope.FULL,
    ) -> ReconciliationOutcome:
        self._set_state(RecoveryState.CONTAINING)
        if self._containment is not None:
            self._containment(account_id)
        if self._stale_runs is not None:
            self._stale_runs.close_stale()
        self._set_state(RecoveryState.OBSERVING)
        self._set_state(RecoveryState.RECONCILING)
        try:
            outcome = self._reconciliation.execute(
                account_id=account_id,
                trigger=trigger,
                correlation_id=correlation_id,
                scope=scope,
            )
        except Exception:
            self._set_state(RecoveryState.FAILED)
            raise

        if (
            outcome.run.result_status is ConsistencyStatus.CONSISTENT
            and outcome.run.confidence is StateConfidence.HIGH
        ):
            self._set_state(RecoveryState.RECOVERED)
        else:
            self._set_state(RecoveryState.BLOCKED)
        return outcome

    def _set_state(self, state: RecoveryState) -> None:
        with self._lock:
            self._state = state
