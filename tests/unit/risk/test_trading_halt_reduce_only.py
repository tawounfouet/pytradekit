"""Trading halt reduce-only qualification."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderSide, OrderType
from pytradekit.portfolio.domain import (
    AccountId,
    Balance,
    PortfolioSnapshot,
    PositionSide,
    PositionView,
)
from pytradekit.risk.adapters import (
    InMemoryPortfolioView,
    InMemoryRiskPolicyRepository,
    InMemoryTradingHaltRepository,
)
from pytradekit.risk.application import (
    EvaluateOrderRisk,
    OrderRiskRequest,
    ReleaseTradingHalt,
    TriggerTradingHalt,
)
from pytradekit.risk.domain import RiskDecision, RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.shared import Currency, InstrumentId, Money, Price, Quantity
from pytradekit.testing import FakeClock

USD = Currency("USD")
NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
PRICE = Price(Decimal("100"), USD)


def test_halt_allows_explicit_risk_reduction_and_can_be_released() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
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
                    cash=Money(Decimal("19000"), USD),
                    updated_at=NOW,
                ),
            ),
            positions=(
                PositionView(
                    instrument_id=instrument_id,
                    quantity=Decimal("10"),
                    side=PositionSide.LONG,
                    average_price=PRICE,
                    market_price=PRICE,
                    market_value=Money(Decimal("1000"), USD),
                    realized_pnl=Money.zero(USD),
                    unrealized_pnl=Money.zero(USD),
                ),
            ),
            nav=Money(Decimal("20000"), USD),
            gross_exposure=Money(Decimal("1000"), USD),
            net_exposure=Money(Decimal("1000"), USD),
            realized_pnl=Money.zero(USD),
            unrealized_pnl=Money.zero(USD),
            leverage=Decimal("0.05"),
        )
    )
    policies = InMemoryRiskPolicyRepository()
    policies.save(
        RiskPolicy(
            id=RiskPolicyId.new(),
            name="global reduce-only",
            scope=RiskScope.GLOBAL,
            limits=(),
            enabled=True,
            version=1,
            allow_reduce_only_when_halted=True,
        )
    )
    halts = InMemoryTradingHaltRepository()
    clock = FakeClock.at(NOW)
    halt = TriggerTradingHalt(repository=halts, clock=clock).execute(
        scope=RiskScope.GLOBAL,
        scope_id=None,
        reason="qualification",
    )
    service = EvaluateOrderRisk(
        policies=policies,
        halts=halts,
        portfolio=portfolio,
        clock=clock,
    )

    result = service.execute(
        OrderRiskRequest(
            account_id=account_id,
            instrument_id=instrument_id,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("5")),
            reference_price=PRICE,
        )
    )

    assert result.decision is RiskDecision.ALLOW
    assert result.projected is not None
    assert result.projected.risk_increasing is False
    assert result.projected.projected_position_quantity == Decimal("5")

    released = ReleaseTradingHalt(repository=halts, clock=clock).execute(halt.id)
    assert released.active is False
    assert halts.get_active(RiskScope.GLOBAL, None) is None
