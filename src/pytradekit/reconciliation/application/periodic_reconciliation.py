"""Deterministic single-process periodic reconciliation scheduler."""

from datetime import datetime, timedelta

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application.reconcile_account import ReconciliationOutcome
from pytradekit.reconciliation.application.workflows import RecoveryWorkflowCoordinator
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import CorrelationId


class PeriodicReconciliation:
    """Run reconciliation at a configured interval without background threads."""

    def __init__(
        self,
        *,
        workflows: RecoveryWorkflowCoordinator,
        clock: ClockPort,
        interval: timedelta,
    ) -> None:
        if interval <= timedelta(0):
            raise ValueError("Periodic reconciliation interval must be positive.")
        self._workflows = workflows
        self._clock = clock
        self._interval = interval
        self._last_attempt: datetime | None = None

    def run_if_due(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome | None:
        now = self._clock.now()
        if self._last_attempt is not None and now - self._last_attempt < self._interval:
            return None
        self._last_attempt = now
        return self._workflows.periodic(
            account_id=account_id,
            correlation_id=correlation_id,
        )
