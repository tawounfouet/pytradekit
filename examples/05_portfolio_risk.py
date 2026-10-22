"""PyTradeKit 0.3 Portfolio and Risk demonstration."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.orders import OrderSide, OrderType, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import HandleExecutionReport, SubmitOrder, SubmitOrderCommand
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
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock

NOW = datetime(2026, 10, 22, 0, 0, tzinfo=UTC)
USD = Currency("USD")
PRICE = Price(Decimal("100"), USD)


def risk_rejection_demo() -> None:
    """Show that a rejected projected order never reaches execution."""
    clock = FakeClock.at(NOW)
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    cash = Money(Decimal("20000"), USD)

    portfolio = InMemoryPortfolioView()
    portfolio.set_snapshot(
        PortfolioSnapshot(
            account_id=account_id,
            as_of=NOW,
            base_currency=USD,
            cash=(
                Balance(
                    account_id=account_id,
                    currency=USD,
                    cash=cash,
                    updated_at=NOW,
                ),
            ),
            positions=(),
            nav=cash,
            gross_exposure=Money.zero(USD),
            net_exposure=Money.zero(USD),
            realized_pnl=Money.zero(USD),
            unrealized_pnl=Money.zero(USD),
            leverage=Decimal("0"),
        )
    )

    policies = InMemoryRiskPolicyRepository()
    policies.save(
        RiskPolicy(
            id=RiskPolicyId.new(),
            name="global-order-limit",
            scope=RiskScope.GLOBAL,
            limits=(MaxOrderSize(Money(Decimal("500"), USD)),),
            enabled=True,
            version=1,
        )
    )

    risk = EvaluateOrderRisk(
        policies=policies,
        halts=InMemoryTradingHaltRepository(),
        portfolio=portfolio,
        clock=clock,
    )
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=clock,
        risk=OrdersRiskEvaluationAdapter(risk),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )

    result = submit.execute(
        SubmitOrderCommand(
            account_id=account_id,
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("10")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            reference_price=PRICE,
        )
    )

    assert result.risk_decision == "reject"
    assert result.submission_status is None
    assert execution.drain_reports(result.order.order_id) == ()

    print(f"risk decision: {result.risk_decision}")
    print(f"violations: {result.risk_violation_codes}")
    print("execution called: no")


def fill_accounting_demo() -> None:
    """Show that one canonical fill updates Order, Position, and Balance."""
    clock = FakeClock.at(NOW)
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()

    positions = InMemoryPositionRepository()
    balances = InMemoryBalanceRepository()
    processed_fills = InMemoryProcessedFillRegistry()
    balances.save(
        Balance(
            account_id=account_id,
            currency=USD,
            cash=Money(Decimal("20000"), USD),
            updated_at=NOW,
        )
    )

    portfolio_effects = OrdersPortfolioEffectAdapter(
        ApplyFillToPortfolio(
            positions=positions,
            balances=balances,
            processed_fills=processed_fills,
        )
    )
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.fill_immediately(price=PRICE),
        clock=clock,
    )
    repository = InMemoryOrderRepository()
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(
        repository=repository,
        portfolio_effects=portfolio_effects,
    )

    result = submit.execute(
        SubmitOrderCommand(
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("10")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            account_id=account_id,
        )
    )

    for report in execution.drain_reports(result.order.order_id):
        handle.execute(report, account_id=account_id)

    position = positions.get(account_id, instrument_id)
    balance = balances.get(account_id, USD)

    assert position is not None
    assert balance is not None
    assert position.quantity == Decimal("10")
    assert balance.cash == Money(Decimal("19000"), USD)

    print(f"position quantity: {position.quantity}")
    print(f"cash after fill: {balance.cash.amount} {balance.currency}")


def main() -> None:
    """Run the milestone 0.3 demonstrations."""
    risk_rejection_demo()
    fill_accounting_demo()


if __name__ == "__main__":
    main()
