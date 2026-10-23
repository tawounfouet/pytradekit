"""Unit tests for IBKR LOT-06.2 read-side reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import ProviderProtocolError
from pytradekit.orders.domain import OrderId
from pytradekit.brokers.adapters.ibkr import (
    IBKRAccountRestrictionsObservation,
    IBKRBrokerSnapshotPort,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRInstrumentMappingResult,
    IBKRReadSideCoverageEvidence,
    IBKRSecurityType,
    IBKRStartupReconciliationGate,
    map_ibkr_stock_contract,
)
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
from pytradekit.shared import CorrelationId, InstrumentId

_NOW = datetime(2026, 10, 23, 6, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


@dataclass
class _AccountValue:
    account: str
    tag: str
    value: str
    currency: str


@dataclass
class _Contract:
    conId: int
    symbol: str
    secType: str
    currency: str


@dataclass
class _PortfolioItem:
    account: str
    contract: _Contract
    position: object
    marketPrice: object
    marketValue: object
    averageCost: object
    unrealizedPNL: object
    realizedPNL: object


@dataclass
class _Order:
    orderId: int
    clientId: int
    permId: int
    orderRef: str


@dataclass
class _OrderStatus:
    status: str
    filled: object
    remaining: object
    avgFillPrice: object
    permId: int
    clientId: int
    orderId: int
    lastFillPrice: object
    whyHeld: str


@dataclass
class _Trade:
    order: _Order
    orderStatus: _OrderStatus
    contract: _Contract


@dataclass
class _Execution:
    execId: str
    acctNumber: str
    exchange: str
    side: str
    shares: object
    price: object
    permId: int
    clientId: int
    orderId: int
    cumQty: object
    avgPrice: object
    orderRef: str
    pendingPriceRevision: bool
    time: datetime


@dataclass
class _Fill:
    contract: _Contract
    execution: _Execution
    time: datetime


class _Client:
    def __init__(self) -> None:
        contract = _Contract(
            conId=265598,
            symbol="AAPL",
            secType="STK",
            currency="USD",
        )
        self.connected = True
        self.account_values: list[object] = [
            _AccountValue("DU1234567", "AccountReady", "true", ""),
            _AccountValue(
                "DU1234567",
                "TotalCashValue",
                "10000.00",
                "USD",
            ),
            _AccountValue(
                "DU1234567",
                "NetLiquidation",
                "15000.00",
                "USD",
            ),
            _AccountValue(
                "DU1234567",
                "BuyingPower",
                "40000.00",
                "USD",
            ),
        ]
        self.portfolio_items: list[object] = [
            _PortfolioItem(
                account="DU1234567",
                contract=contract,
                position=10,
                marketPrice=210,
                marketValue=2100,
                averageCost=200,
                unrealizedPNL=100,
                realizedPNL=25,
            )
        ]
        self.trade_items: list[object] = [
            _Trade(
                order=_Order(
                    orderId=42,
                    clientId=1,
                    permId=9001,
                    orderRef="ptk-order-1",
                ),
                orderStatus=_OrderStatus(
                    status="Submitted",
                    filled=0,
                    remaining=10,
                    avgFillPrice=0,
                    permId=9001,
                    clientId=1,
                    orderId=42,
                    lastFillPrice=0,
                    whyHeld="",
                ),
                contract=contract,
            )
        ]
        self.fill_items: list[object] = [
            _Fill(
                contract=contract,
                execution=_Execution(
                    execId="0001.01",
                    acctNumber="DU1234567",
                    exchange="NASDAQ",
                    side="BOT",
                    shares=2,
                    price=205,
                    permId=9001,
                    clientId=1,
                    orderId=42,
                    cumQty=2,
                    avgPrice=205,
                    orderRef="ptk-order-1",
                    pendingPriceRevision=False,
                    time=_NOW,
                ),
                time=_NOW,
            )
        ]

    def isConnected(self) -> bool:
        return self.connected

    def accountValues(self, account: str = "") -> list[object]:
        return list(self.account_values)

    def portfolio(self, account: str = "") -> list[object]:
        return list(self.portfolio_items)

    def trades(self) -> list[object]:
        return list(self.trade_items)

    def fills(self) -> list[object]:
        return list(self.fill_items)


class _InstrumentResolver:
    def __init__(self, mapping: IBKRInstrumentMappingResult | None) -> None:
        self.mapping = mapping

    def resolve(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> IBKRInstrumentMappingResult | None:
        if self.mapping is None:
            return None
        if self.mapping.identity.external_id != str(contract_id):
            return None
        if self.mapping.identity.external_symbol != symbol:
            return None
        return self.mapping


class _IdentityResolver:
    def __init__(self) -> None:
        self.order_id: OrderId | None = None

    def resolve_order_id(
        self,
        external_order_id: str,
        client_order_id: str | None = None,
    ) -> OrderId | None:
        if external_order_id == "9001":
            return self.order_id
        return None


class _Restrictions:
    def __init__(self, available: bool = True) -> None:
        self.available = available

    def get(
        self,
        external_account_id: str,
    ) -> IBKRAccountRestrictionsObservation | None:
        if not self.available:
            return None
        return IBKRAccountRestrictionsObservation(
            trading_blocked=False,
            account_blocked=False,
            evidence_source="controlled-paper-readiness-fixture",
        )


def _coverage() -> IBKRReadSideCoverageEvidence:
    return IBKRReadSideCoverageEvidence(
        orders_complete=True,
        fills_complete=True,
        positions_complete=True,
        account_complete=True,
        evidence_source="deterministic-lot06.2-fixture",
    )


def _instrument() -> IBKRInstrumentMappingResult:
    return map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=IBKRContractRecord(
                contract_id=IBKRContractId(265598),
                symbol="AAPL",
                security_type=IBKRSecurityType.STOCK,
                exchange="SMART",
                primary_exchange="NASDAQ",
                currency="USD",
                local_symbol="AAPL",
            ),
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=InstrumentId.new(),
    )


def _snapshot_port(
    *,
    client: _Client | None = None,
    mapping: IBKRInstrumentMappingResult | None = None,
    restrictions_available: bool = True,
) -> IBKRBrokerSnapshotPort:
    identity = _IdentityResolver()
    identity.order_id = None
    return IBKRBrokerSnapshotPort(
        client=client or _Client(),
        expected_external_account_id="DU1234567",
        instruments=_InstrumentResolver(
            _instrument() if mapping is None else mapping
        ),
        identities=identity,
        restrictions=_Restrictions(restrictions_available),
        coverage=_coverage(),
        clock=_Clock(),
    )


def test_full_read_side_capture_normalizes_provider_truth() -> None:
    account_id = AccountId.new()
    port = _snapshot_port()

    snapshot = port.capture(
        account_id=account_id,
        scope=ReconciliationScope.FULL,
    )

    assert snapshot.provider == "ibkr"
    assert snapshot.completeness is SnapshotCompleteness.COMPLETE
    assert len(snapshot.orders) == 1
    assert snapshot.orders[0].external_order_id == "9001"
    assert snapshot.orders[0].status == "ACCEPTED"
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].external_fill_id == "0001.01"
    assert snapshot.fills[0].origin.value == "UNKNOWN_EXTERNAL"
    assert len(snapshot.positions) == 1
    assert snapshot.positions[0].quantity == Decimal("10")
    assert len(snapshot.balances) == 1
    assert snapshot.balances[0].cash == Decimal("10000.00")
    assert port.last_stats is not None
    assert port.last_stats.complete


def test_missing_restriction_evidence_marks_snapshot_partial() -> None:
    snapshot = _snapshot_port(restrictions_available=False).capture(
        account_id=AccountId.new(),
        scope=ReconciliationScope.FULL,
    )

    assert snapshot.completeness is SnapshotCompleteness.PARTIAL
    assert snapshot.balances == ()


def test_unresolved_position_mapping_marks_snapshot_partial() -> None:
    client = _Client()
    port = IBKRBrokerSnapshotPort(
        client=client,
        expected_external_account_id="DU1234567",
        instruments=_InstrumentResolver(None),
        identities=_IdentityResolver(),
        restrictions=_Restrictions(),
        coverage=_coverage(),
        clock=_Clock(),
    )

    snapshot = port.capture(
        account_id=AccountId.new(),
        scope=ReconciliationScope.FULL,
    )

    assert snapshot.completeness is SnapshotCompleteness.PARTIAL
    assert snapshot.positions == ()


def test_disconnected_session_fails_closed_before_capture() -> None:
    client = _Client()
    client.connected = False

    with pytest.raises(ProviderProtocolError, match="active synchronized"):
        _snapshot_port(client=client).capture(
            account_id=AccountId.new(),
            scope=ReconciliationScope.FULL,
        )


def _startup_report(*, ready: bool = True) -> StartupReadinessReport:
    return StartupReadinessReport(
        provider="ibkr",
        environment="PAPER",
        account="***4567",
        checks=(
            ReadinessCheck(
                name="transport",
                status=(
                    ReadinessCheckStatus.PASS
                    if ready
                    else ReadinessCheckStatus.FAIL
                ),
                detail="transport",
            ),
        ),
    )


def _outcome(
    *,
    status: ConsistencyStatus,
    confidence: StateConfidence,
) -> ReconciliationOutcome:
    account_id = AccountId.new()
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
        result_status=status,
        confidence=confidence,
        mismatch_count=0,
        critical_mismatch_count=0,
    )
    return ReconciliationOutcome(
        run=run,
        mismatches=(),
        resolutions=(),
    )


class _Workflow:
    def __init__(self, outcome: ReconciliationOutcome) -> None:
        self.outcome = outcome
        self.calls = 0

    def startup(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        self.calls += 1
        return self.outcome


def test_startup_gate_proves_consistent_high_but_keeps_writes_blocked() -> None:
    workflow = _Workflow(
        _outcome(
            status=ConsistencyStatus.CONSISTENT,
            confidence=StateConfidence.HIGH,
        )
    )
    gate = IBKRStartupReconciliationGate(
        account_id=AccountId.new(),
        workflows=workflow,
    )

    report = gate.evaluate(_startup_report())

    assert report.state is TradingReadinessState.NOT_READY
    assert report.consistency_status is ConsistencyStatus.CONSISTENT
    assert report.state_confidence is StateConfidence.HIGH
    assert "IBKR economic write path is not qualified yet" in report.gaps
    assert workflow.calls == 1


def test_startup_gate_blocks_incomplete_reconciliation_evidence() -> None:
    workflow = _Workflow(
        _outcome(
            status=ConsistencyStatus.UNKNOWN,
            confidence=StateConfidence.LOW,
        )
    )
    gate = IBKRStartupReconciliationGate(
        account_id=AccountId.new(),
        workflows=workflow,
    )

    report = gate.evaluate(_startup_report())

    assert report.state is TradingReadinessState.NOT_READY
    assert report.gaps


def test_startup_gate_does_not_run_when_transport_is_not_ready() -> None:
    workflow = _Workflow(
        _outcome(
            status=ConsistencyStatus.CONSISTENT,
            confidence=StateConfidence.HIGH,
        )
    )
    gate = IBKRStartupReconciliationGate(
        account_id=AccountId.new(),
        workflows=workflow,
    )

    report = gate.evaluate(_startup_report(ready=False))

    assert report.state is TradingReadinessState.NOT_READY
    assert workflow.calls == 0
