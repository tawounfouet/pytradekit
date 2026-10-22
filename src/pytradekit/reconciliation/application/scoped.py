"""Scoped reconciliation use cases."""

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application.reconcile_account import (
    ReconcileAccount,
    ReconciliationOutcome,
)
from pytradekit.reconciliation.domain import ReconciliationScope, ReconciliationTrigger
from pytradekit.shared import CorrelationId


class _ScopedReconciliation:
    scope: ReconciliationScope

    def __init__(self, service: ReconcileAccount) -> None:
        self._service = service

    def execute(
        self,
        *,
        account_id: AccountId,
        trigger: ReconciliationTrigger,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._service.execute(
            account_id=account_id,
            trigger=trigger,
            correlation_id=correlation_id,
            scope=self.scope,
        )


class ReconcileOrders(_ScopedReconciliation):
    scope = ReconciliationScope.ORDERS


class ReconcileFills(_ScopedReconciliation):
    scope = ReconciliationScope.FILLS


class ReconcilePositions(_ScopedReconciliation):
    scope = ReconciliationScope.POSITIONS


class ReconcileBalances(_ScopedReconciliation):
    scope = ReconciliationScope.BALANCES
