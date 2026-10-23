"""Qualification tests for IBKR LOT-06.2 read-side reconciliation."""

from datetime import UTC, datetime

from pytradekit.brokers.adapters.ibkr import (
    IBKRAccountRestrictionsObservation,
    IBKRBrokerSnapshotPort,
    IBKRContractId,
    IBKRInstrumentMappingResult,
    IBKRReadSideCoverageEvidence,
    IBKRStartupReconciliationGate,
)
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application import ReconciliationOutcome
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    SnapshotCompleteness,
    StateConfidence,
)
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    StartupReadinessReport,
    TradingReadinessState,
)
from pytradekit.shared import CorrelationId

_NOW = datetime(2026, 10, 23, 6, 30, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Value:
    def __init__(
        self,
        account: str,
        tag: str,
        value: str,
        currency: str,
    ) -> None:
        self.account = account
        self.tag = tag
        self.value = value
        self.currency = currency


class _EmptyReadClient:
    def isConnected(self) -> bool:
        return True

    def accountValues(self, account: str = "") -> list[object]:
        return [
            _Value("DU1234567", "AccountReady", "true", ""),
            _Value(
                "DU1234567",
                "TotalCashValue",
                "25000.00",
                "USD",
            ),
            _Value(
                "DU1234567",
                "NetLiquidation",
                "25000.00",
                "USD",
            ),
        ]

    def portfolio(self, account: str = "") -> list[object]:
        return []

    def trades(self) -> list[object]:
        return []

    def fills(self) -> list[object]:
        return []


class _NoInstrumentLookup:
    def resolve(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> IBKRInstrumentMappingResult | None:
        return None


class _NoOrderLookup:
    def resolve_order_id(
        self,
        external_order_id: str,
        client_order_id: str | None = None,
    ) -> OrderId | None:
        return None


class _Restrictions:
    def get(
        self,
        external_account_id: str,
    ) -> IBKRAccountRestrictionsObservation | None:
        return IBKRAccountRestrictionsObservation(
            trading_blocked=False,
            account_blocked=False,
            evidence_source="deterministic-lot06.2-fixture",
        )


def _coverage() -> IBKRReadSideCoverageEvidence:
    return IBKRReadSideCoverageEvidence(
        orders_complete=True,
        fills_complete=True,
        positions_complete=True,
        account_complete=True,
        evidence_source="deterministic-lot06.2-fixture",
    )


def _completed_outcome(account_id: AccountId) -> ReconciliationOutcome:
    run = ReconciliationRun.create(
        account_id=account_id,
        scope=ReconciliationScope.FULL,
        trigger=ReconciliationTrigger.STARTUP,
        started_at=_NOW,
        correlation_id=CorrelationId.new(),
    )
    run.transition_to(ReconciliationRunStatus.CAPTURING)
    run.transition_to(ReconciliationRunStatus.COMPARING)
    run.transition_to(ReconciliationRunStatus.VERIFYING)
    run.complete(
        completed_at=_NOW,
        result_status=ConsistencyStatus.CONSISTENT,
        confidence=StateConfidence.HIGH,
        mismatch_count=0,
        critical_mismatch_count=0,
    )
    return ReconciliationOutcome(
        run=run,
        mismatches=(),
        resolutions=(),
    )


class _Workflow:
    def __init__(self, account_id: AccountId) -> None:
        self._outcome = _completed_outcome(account_id)

    def startup(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._outcome


def test_lot06_2_complete_read_side_can_reconcile_without_write_admission() -> None:
    account_id = AccountId.new()
    broker = IBKRBrokerSnapshotPort(
        client=_EmptyReadClient(),
        expected_external_account_id="DU1234567",
        instruments=_NoInstrumentLookup(),
        identities=_NoOrderLookup(),
        restrictions=_Restrictions(),
        coverage=_coverage(),
        clock=_Clock(),
    )
    snapshot = broker.capture(
        account_id=account_id,
        scope=ReconciliationScope.FULL,
    )

    assert snapshot.completeness is SnapshotCompleteness.COMPLETE
    assert snapshot.orders == ()
    assert snapshot.fills == ()
    assert snapshot.positions == ()
    assert snapshot.balances[0].cash == 25000

    gate = IBKRStartupReconciliationGate(
        account_id=account_id,
        workflows=_Workflow(account_id),
    )
    report = gate.evaluate(
        StartupReadinessReport(
            provider="ibkr",
            environment="PAPER",
            account="***4567",
            checks=(
                ReadinessCheck(
                    name="transport",
                    status=ReadinessCheckStatus.PASS,
                    detail="qualified deterministic transport fixture",
                ),
            ),
        )
    )

    assert report.consistency_status is ConsistencyStatus.CONSISTENT
    assert report.state_confidence is StateConfidence.HIGH
    assert report.state is TradingReadinessState.NOT_READY
    assert "IBKR economic write path is not qualified yet" in report.gaps
