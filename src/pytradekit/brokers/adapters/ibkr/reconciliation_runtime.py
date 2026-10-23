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
from pytradekit.runtime import TradingReadinessReport
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
from .startup_reconciliation import IBKRStartupReconciliationGate

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
    gate: IBKRStartupReconciliationGate
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
        return self.gate.evaluate(startup)

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
        gate=IBKRStartupReconciliationGate(
            account_id=account_id,
            workflows=workflows,
        ),
        session=evidence_session,
    )
