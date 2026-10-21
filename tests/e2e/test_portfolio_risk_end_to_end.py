"""End-to-end qualification of Portfolio and Risk integration."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders import Order, OrderSide, OrderStatus, OrderType, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import (
    HandleExecutionReport,
    SubmitOrder,
    SubmitOrderCommand,
)
from pytradekit.portfolio.adapters import (
    InMemoryBalanceRepository,
    InMemoryPositionRepository,
    InMemoryProcessedFillRegistry,
    OrdersPortfolioEffectAdapter,
)
from pytradekit.portfolio.application import ApplyFillToPortfolio
from pytradekit.portfolio.domain import AccountId, Balance, PortfolioSnapshot
from pytradekit.risk.adapters import (
    InMemoryPortfolioView,
    InMemoryRiskPolicyRepository,
    InMemoryTradingHaltRepository,
    OrdersRiskEvaluationAdapter,
)
from pytradekit.risk.application import EvaluateOrderRisk
from pytradekit.risk.domain import RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.risk.domain.rules import MaxOrderSize
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
)
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
USD = Currency("USD")
PRICE = Price(Decimal("100"), USD)


class CountingExecution:
    """Execution port spy used to prove rejected orders never reach a broker."""

    def __init__(self) -> None:
        self.submit_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        """Record the call and acknowledge submission."""
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=f"spy-{order.id}",
        )

    def cancel(self, order: Order) -> CancelResult:
        """Acknowledge cancellation for protocol completeness."""
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        """Return no additional execution state."""
        return None


def _empty_snapshot(account_id: AccountId, cash: str = "20000") -> PortfolioSnapshot:
    value = Money(Decimal(cash), USD)
    return PortfolioSnapshot(
        account_id=account_id,
        as_of=NOW,
        base_currency=USD,
        cash=(
            Balance(
                account_id=account_id,
                currency=USD,
                cash=value,
                updated_at=NOW,
            ),
        ),
        positions=(),
        nav=value,
        gross_exposure=Money.zero(USD),
        net_exposure=Money.zero(USD),
        realized_pnl=Money.zero(USD),
        unrealized_pnl=Money.zero(USD),
        leverage=Decimal("0"),
    )


def test_risk_rejection_prevents_execution_port_call() -> None:
    account_id = AccountId.new()
    portfolio = InMemoryPortfolioView()
    portfolio.set_snapshot(_empty_snapshot(account_id))
    policies = InMemoryRiskPolicyRepository()
    policies.save(
        RiskPolicy(
            id=RiskPolicyId.new(),
            name="global",
            scope=RiskScope.GLOBAL,
            limits=(MaxOrderSize(Money(Decimal("500"), USD)),),
            enabled=True,
            version=1,
        )
    )
    risk_service = EvaluateOrderRisk(
        policies=policies,
        halts=InMemoryTradingHaltRepository(),
        portfolio=portfolio,
        clock=FakeClock.at(NOW),
    )
    execution = CountingExecution()
    repository = InMemoryOrderRepository()
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=FakeClock.at(NOW),
        risk=OrdersRiskEvaluationAdapter(risk_service),
    )

    result = submit.execute(
        SubmitOrderCommand(
            account_id=account_id,
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("10")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            reference_price=PRICE,
        )
    )

    assert result.order.status is OrderStatus.VALIDATED
    assert result.submission_status is None
    assert result.risk_decision == "reject"
    assert result.risk_violation_codes == ("MAX_ORDER_SIZE_EXCEEDED",)
    assert execution.submit_calls == 0


def test_fill_updates_order_position_and_cash_once() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    positions = InMemoryPositionRepository()
    balances = InMemoryBalanceRepository()
    processed = InMemoryProcessedFillRegistry()
    balances.save(
        Balance(
            account_id=account_id,
            currency=USD,
            cash=Money(Decimal("20000"), USD),
            updated_at=NOW,
        )
    )
    effects = OrdersPortfolioEffectAdapter(
        ApplyFillToPortfolio(
            positions=positions,
            balances=balances,
            processed_fills=processed,
        )
    )
    clock = FakeClock.at(NOW)
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.fill_immediately(price=PRICE),
        clock=clock,
    )
    repository = InMemoryOrderRepository()
    submit = SubmitOrder(repository=repository, execution=execution, clock=clock)
    handle = HandleExecutionReport(repository=repository, portfolio_effects=effects)

    result = submit.execute(
        SubmitOrderCommand(
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("10")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
        )
    )
    reports = execution.drain_reports(result.order.order_id)
    fill_report = next(report for report in reports if report.fill is not None)

    for report in reports:
        handle.execute(report, account_id=account_id)
    handle.execute(fill_report, account_id=account_id)

    position = positions.get(account_id, instrument_id)
    balance = balances.get(account_id, USD)
    order = repository.get(result.order.order_id)

    assert order is not None
    assert order.status is OrderStatus.FILLED
    assert position is not None
    assert position.quantity == Decimal("10")
    assert balance is not None
    assert balance.cash == Money(Decimal("19000"), USD)
