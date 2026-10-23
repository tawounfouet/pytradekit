"""IBKR startup reconciliation over the generic provider-neutral pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.adapters.postgres import (
    PostgresInternalSnapshotPort,
    PostgresOrderIdentityResolver,
    PostgresReconciliationRepository,
)
from pytradekit.reconciliation.application import (
    ConsistencyAdmissionPolicy,
    ConsistencyRegistry,
    ReconcileAccount,
    ReconciliationOutcome,
    RecoveryWorkflowCoordinator,
    StaleRunRecovery,
)
from pytradekit.reconciliation.domain import ConsistencyStatus, StateConfidence
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    TradingReadinessReport,
)
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import CorrelationId

from .discovery import IBKR_PROVIDER_KEY
from .read_side import (
    IBKRAccountRestrictionsProvider,
    IBKRBrokerSnapshotPort,
    IBKRInstrumentResolver,
    IBKRReadSideClient,
)
from .runtime import IBKRPaperConnectionRuntime

IBKR_RECONCILIATION_RUNTIME_VERSION = "0.8.0b3-lot06.2"


class IBKRRuntimeReadClient:
    """Proxy synchronized provider reads through the connected PAPER runtime."""

    def __init__(self, runtime: IBKRPaperConnectionRuntime) -> None:
        self._runtime = runtime

    def _client(self) -> IBKRReadSideClient:
        return cast(IBKRReadSideClient, self._runtime.read_client())

    def isConnected(self) -> bool:
        try:
            return self._client().isConnected()
        except Exception:
            return False

    def accountValues(self, account: str = "") -> list[object]:
        return self._client().accountValues(account)

    def portfolio(self, account: str = "") -> list[object]:
        return self._client().portfolio(account)

    def trades(self) -> list[object]:
        return self._client().trades()

    def fills(self) -> list[object]:
        return self._client().fills()


@dataclass(slots=True)
class IBKRStartupReconciliationRuntime:
    """Own startup connection and generic read-side reconciliation evidence."""

    connection: IBKRPaperConnectionRuntime
    account_id: AccountId
    workflows: RecoveryWorkflowCoordinator
    registry: ConsistencyRegistry
    consistency_gate: ConsistencyAdmissionPolicy
    session: Session

    @property
    def reconciliation_complete(self) -> bool:
        evidence = self.registry.get(self.account_id)
        if evidence is None:
            return False
        return (
            evidence.status is ConsistencyStatus.CONSISTENT
            and evidence.confidence is StateConfidence.HIGH
        )

    def start(self) -> TradingReadinessReport:
        """Connect and reconcile while keeping economic writes fail-closed."""

        startup = self.connection.start()
        checks = list(startup.checks)
        gaps: list[str] = []

        if not startup.ready_for_startup:
            gaps.append("IBKR PAPER connection startup is not ready")
            gaps.append(
                "economic write runtime is not yet qualified by LOT-06.2"
            )
            return self._report(
                checks=checks,
                gaps=gaps,
                consistency_status=None,
                state_confidence=None,
            )

        try:
            outcome = self.workflows.startup(
                account_id=self.account_id,
                correlation_id=CorrelationId.new(),
            )
        except Exception as exc:
            self.registry.clear(self.account_id)
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
            gaps.append("IBKR startup reconciliation did not complete")
            gaps.append(
                "economic write runtime is not yet qualified by LOT-06.2"
            )
            return self._report(
                checks=checks,
                gaps=gaps,
                consistency_status=None,
                state_confidence=None,
            )

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
                    "IBKR broker and durable state reconciled CONSISTENT/HIGH."
                    if safe
                    else "IBKR startup reconciliation did not prove safe convergence."
                ),
            )
        )
        if not safe:
            gaps.append(
                "IBKR startup reconciliation did not prove CONSISTENT/HIGH"
            )

        gaps.append(
            "economic write runtime is not yet qualified by LOT-06.2"
        )
        return self._report(
            checks=checks,
            gaps=gaps,
            consistency_status=status,
            state_confidence=confidence,
        )

    def periodic(self) -> ReconciliationOutcome:
        return self.workflows.periodic(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def reconnect(self) -> ReconciliationOutcome:
        return self.workflows.reconnect(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def submit_uncertainty(self) -> ReconciliationOutcome:
        return self.workflows.submit_uncertainty(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def stop(self) -> None:
        try:
            self.connection.stop()
        finally:
            self.session.close()

    def _report(
        self,
        *,
        checks: list[ReadinessCheck],
        gaps: list[str],
        consistency_status: ConsistencyStatus | None,
        state_confidence: StateConfidence | None,
    ) -> TradingReadinessReport:
        return TradingReadinessReport(
            provider=IBKR_PROVIDER_KEY,
            environment="PAPER",
            account=self.connection.profile.masked_account_id,
            checks=tuple(checks),
            gaps=tuple(dict.fromkeys(gaps)),
            consistency_status=consistency_status,
            state_confidence=state_confidence,
        )


def build_ibkr_startup_reconciliation_runtime(
    *,
    connection: IBKRPaperConnectionRuntime,
    account_id: AccountId,
    instruments: IBKRInstrumentResolver,
    restrictions: IBKRAccountRestrictionsProvider,
    session_factory: sessionmaker[Session],
    clock: ClockPort,
) -> IBKRStartupReconciliationRuntime:
    """Compose LOT-06.2 on the existing generic reconciliation machinery."""

    evidence_session = session_factory()
    repository = PostgresReconciliationRepository(evidence_session)
    identities = PostgresOrderIdentityResolver(session_factory)
    internal = PostgresInternalSnapshotPort(
        session_factory=session_factory,
        clock=clock,
    )
    broker = IBKRBrokerSnapshotPort(
        client=IBKRRuntimeReadClient(connection),
        expected_external_account_id=connection.profile.expected_account_id,
        instruments=instruments,
        identities=identities,
        restrictions=restrictions,
        clock=clock,
    )
    registry = ConsistencyRegistry()
    service = ReconcileAccount(
        repository=repository,
        internal_snapshots=internal,
        broker_snapshots=broker,
        clock=clock,
        evidence_sink=registry,
    )
    stale_runs = StaleRunRecovery(
        repository=repository,
        clock=clock,
        stale_after=timedelta(minutes=15),
    )
    workflows = RecoveryWorkflowCoordinator(
        reconciliation=service,
        stale_runs=stale_runs,
        containment=registry.clear,
    )
    return IBKRStartupReconciliationRuntime(
        connection=connection,
        account_id=account_id,
        workflows=workflows,
        registry=registry,
        consistency_gate=ConsistencyAdmissionPolicy(registry),
        session=evidence_session,
    )
