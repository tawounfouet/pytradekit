"""Generic milestone 0.6 reconciliation integrated with Alpaca PAPER."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from sqlalchemy.orm import Session

from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.adapters.postgres import (
    PostgresInternalSnapshotPort,
    PostgresOrderIdentityResolver,
    PostgresReconciliationRepository,
    PostgresResolutionExecutor,
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

from .reconciliation import AlpacaActivityClient, AlpacaExternalActivityReader
from .reconciliation_snapshot import (
    AlpacaBrokerSnapshotPort,
    AlpacaOrderInventoryClient,
)
from .runtime import AlpacaPaperRuntimeComposition
from .snapshots import AlpacaMarketDataSnapshots

UowFactory = Callable[[], PostgresUnitOfWork]


@dataclass(slots=True)
class AlpacaGenericReconciliationRuntime:
    """Own the generic reconciliation service and its durable evidence session."""

    account_id: AccountId
    workflows: RecoveryWorkflowCoordinator
    consistency_gate: ConsistencyAdmissionPolicy
    registry: ConsistencyRegistry
    session: Session

    def startup(self, base: TradingReadinessReport) -> TradingReadinessReport:
        """Run generic reconciliation after the qualified 0.5 startup baseline."""

        if not base.trading_ready:
            return base

        checks = list(base.checks)
        gaps = list(base.gaps)
        try:
            outcome = self.workflows.startup(
                account_id=self.account_id,
                correlation_id=CorrelationId.new(),
            )
        except Exception as exc:
            checks.append(
                ReadinessCheck(
                    name="generic_reconciliation",
                    status=ReadinessCheckStatus.FAIL,
                    detail=(
                        "Generic reconciliation failed safely: "
                        f"{type(exc).__name__}."
                    ),
                )
            )
            gaps.append("generic reconciliation did not complete")
            return TradingReadinessReport(
                provider=base.provider,
                environment=base.environment,
                account=base.account,
                checks=tuple(checks),
                gaps=tuple(gaps),
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
                name="generic_reconciliation",
                status=(
                    ReadinessCheckStatus.PASS
                    if safe
                    else ReadinessCheckStatus.FAIL
                ),
                detail=(
                    "Generic reconciliation proved CONSISTENT/HIGH."
                    if safe
                    else "Generic reconciliation completed without safe convergence."
                ),
            )
        )
        if not safe:
            gaps.append("generic reconciliation did not prove CONSISTENT/HIGH")

        return TradingReadinessReport(
            provider=base.provider,
            environment=base.environment,
            account=base.account,
            checks=tuple(checks),
            gaps=tuple(gaps),
            consistency_status=status,
            state_confidence=confidence,
        )

    def periodic(self) -> ReconciliationOutcome:
        """Run periodic reconciliation while fail-closing admission first."""

        return self.workflows.periodic(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def reconnect(self) -> ReconciliationOutcome:
        """Reconcile after transport reconnect before risk may resume."""

        return self.workflows.reconnect(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def submit_uncertainty(self) -> ReconciliationOutcome:
        """Reconcile after an uncertain provider submission outcome."""

        return self.workflows.submit_uncertainty(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def incident(self) -> ReconciliationOutcome:
        """Run incident-triggered reconciliation under containment."""

        return self.workflows.incident(
            account_id=self.account_id,
            correlation_id=CorrelationId.new(),
        )

    def close(self) -> None:
        """Close the dedicated durable evidence session."""

        self.session.close()


def build_alpaca_generic_reconciliation_runtime(
    *,
    composition: AlpacaPaperRuntimeComposition,
    snapshots: AlpacaMarketDataSnapshots,
    account_id: AccountId,
    clock: ClockPort,
    uow_factory: UowFactory,
) -> AlpacaGenericReconciliationRuntime:
    """Assemble the provider-neutral 0.6 pipeline for the Alpaca PAPER runtime."""

    evidence_session = composition.session_factory()
    repository = PostgresReconciliationRepository(evidence_session)
    identities = PostgresOrderIdentityResolver(composition.session_factory)
    internal = PostgresInternalSnapshotPort(
        session_factory=composition.session_factory,
        clock=clock,
    )
    fills = AlpacaExternalActivityReader(
        client=cast(AlpacaActivityClient, composition.read_client),
        orders=identities,
    )
    broker = AlpacaBrokerSnapshotPort(
        snapshots=snapshots,
        orders_client=cast(
            AlpacaOrderInventoryClient,
            composition.read_client,
        ),
        fills=fills,
        identities=identities,
        clock=clock,
    )
    registry = ConsistencyRegistry()
    service = ReconcileAccount(
        repository=repository,
        internal_snapshots=internal,
        broker_snapshots=broker,
        clock=clock,
        executor=PostgresResolutionExecutor(uow_factory),
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
    return AlpacaGenericReconciliationRuntime(
        account_id=account_id,
        workflows=workflows,
        consistency_gate=ConsistencyAdmissionPolicy(registry),
        registry=registry,
        session=evidence_session,
    )
