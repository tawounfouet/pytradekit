"""IBKR startup reconciliation gate for PAPER admission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application import ReconciliationOutcome
from pytradekit.reconciliation.domain import ConsistencyStatus, StateConfidence
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    StartupReadinessReport,
    TradingReadinessReport,
)
from pytradekit.shared import CorrelationId

from .discovery import IBKR_PROVIDER_KEY

IBKR_STARTUP_RECONCILIATION_VERSION = "0.8.0b3-lot06.2"


class IBKRStartupReconciliationWorkflow(Protocol):
    """Generic recovery workflow surface required by the IBKR startup gate."""

    def startup(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        """Run full startup reconciliation under containment."""

        ...


@dataclass(slots=True)
class IBKRStartupReconciliationGate:
    """Prove fresh read-side convergence while keeping economic writes closed."""

    account_id: AccountId
    workflows: IBKRStartupReconciliationWorkflow

    def evaluate(
        self,
        startup: StartupReadinessReport,
    ) -> TradingReadinessReport:
        """Convert startup readiness into trading readiness only after reconciliation."""

        checks = list(startup.checks)
        gaps: list[str] = []

        if startup.provider != IBKR_PROVIDER_KEY:
            checks.append(
                ReadinessCheck(
                    name="provider_identity",
                    status=ReadinessCheckStatus.FAIL,
                    detail="IBKR reconciliation gate received another provider.",
                )
            )
            gaps.append("provider identity mismatch")
            return self._report(startup, checks, gaps)

        if not startup.ready_for_startup:
            checks.append(
                ReadinessCheck(
                    name="startup_reconciliation",
                    status=ReadinessCheckStatus.FAIL,
                    detail=(
                        "Startup reconciliation is blocked until transport "
                        "readiness succeeds."
                    ),
                )
            )
            gaps.append("startup transport prerequisites are not ready")
            return self._report(startup, checks, gaps)

        try:
            outcome = self.workflows.startup(
                account_id=self.account_id,
                correlation_id=CorrelationId.new(),
            )
        except Exception as exc:
            checks.append(
                ReadinessCheck(
                    name="startup_reconciliation",
                    status=ReadinessCheckStatus.FAIL,
                    detail=(
                        "IBKR startup reconciliation failed safely "
                        f"({type(exc).__name__})."
                    ),
                )
            )
            gaps.append("startup reconciliation did not complete")
            return self._report(startup, checks, gaps)

        status = outcome.run.result_status
        confidence = outcome.run.confidence
        safe = (
            status is ConsistencyStatus.CONSISTENT
            and confidence is StateConfidence.HIGH
        )
        checks.append(
            ReadinessCheck(
                name="startup_reconciliation",
                status=(
                    ReadinessCheckStatus.PASS
                    if safe
                    else ReadinessCheckStatus.FAIL
                ),
                detail=(
                    "IBKR startup reconciliation proved CONSISTENT/HIGH."
                    if safe
                    else (
                        "IBKR startup reconciliation completed without "
                        "CONSISTENT/HIGH evidence."
                    )
                ),
            )
        )
        if not safe:
            gaps.append(
                "startup reconciliation did not prove CONSISTENT/HIGH"
            )

        checks.append(
            ReadinessCheck(
                name="economic_write_admission",
                status=ReadinessCheckStatus.FAIL,
                detail=(
                    "LOT-06.2 qualifies read-side convergence only; "
                    "IBKR economic writes remain blocked."
                ),
            )
        )
        gaps.append("IBKR economic write path is not qualified yet")

        return TradingReadinessReport(
            provider=startup.provider,
            environment=startup.environment,
            account=startup.account,
            checks=tuple(checks),
            gaps=tuple(gaps),
            consistency_status=status,
            state_confidence=confidence,
        )

    @staticmethod
    def _report(
        startup: StartupReadinessReport,
        checks: list[ReadinessCheck],
        gaps: list[str],
    ) -> TradingReadinessReport:
        return TradingReadinessReport(
            provider=startup.provider,
            environment=startup.environment,
            account=startup.account,
            checks=tuple(checks),
            gaps=tuple(gaps),
            consistency_status=None,
            state_confidence=None,
        )
