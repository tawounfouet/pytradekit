"""Consistency and confidence safety integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from pytradekit.orders.ports import ConsistencyGatePort
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationRunId,
    StateConfidence,
)
from pytradekit.strategy.ports import StrategyAdmissionPort


class UnsafeConsistencyError(RuntimeError):
    """Raised when a risk-increasing action lacks safe reconciliation evidence."""


@dataclass(frozen=True, slots=True)
class ConsistencyEvidence:
    """Latest completed consistency evidence for one account."""

    run_id: ReconciliationRunId
    account_id: AccountId
    status: ConsistencyStatus
    confidence: StateConfidence
    observed_at: datetime


class ConsistencyRegistry:
    """Thread-safe latest-evidence registry used by runtime admission."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._evidence: dict[AccountId, ConsistencyEvidence] = {}

    def record(self, run: ReconciliationRun) -> None:
        if run.result_status is None or run.confidence is None or run.completed_at is None:
            raise ValueError("Only completed reconciliation evidence can be recorded.")
        evidence = ConsistencyEvidence(
            run_id=run.id,
            account_id=run.account_id,
            status=run.result_status,
            confidence=run.confidence,
            observed_at=run.completed_at,
        )
        with self._lock:
            current = self._evidence.get(run.account_id)
            if current is None or evidence.observed_at >= current.observed_at:
                self._evidence[run.account_id] = evidence

    def get(self, account_id: AccountId) -> ConsistencyEvidence | None:
        with self._lock:
            return self._evidence.get(account_id)

    def clear(self, account_id: AccountId) -> None:
        """Invalidate prior admission evidence before an uncertainty workflow."""

        with self._lock:
            self._evidence.pop(account_id, None)


class ConsistencyAdmissionPolicy(ConsistencyGatePort, StrategyAdmissionPort):
    """Allow new risk only for CONSISTENT + HIGH evidence."""

    def __init__(self, registry: ConsistencyRegistry) -> None:
        self._registry = registry

    def ensure_risk_increase_allowed(self, account_id: AccountId) -> None:
        if not self.allow_new_targets(account_id):
            raise UnsafeConsistencyError(
                "Risk increase is blocked by reconciliation consistency or confidence."
            )

    def allow_new_targets(self, account_id: AccountId) -> bool:
        """Return whether strategy and order paths may create new risk targets."""

        evidence = self._registry.get(account_id)
        if evidence is None:
            return False
        return (
            evidence.status is ConsistencyStatus.CONSISTENT
            and evidence.confidence is StateConfidence.HIGH
        )
