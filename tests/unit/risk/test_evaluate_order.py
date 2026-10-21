"""EvaluateOrderRisk and TradingHalt unit tests."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderSide, OrderType
from pytradekit.portfolio.domain import AccountId, Balance, PortfolioSnapshot
from pytradekit.risk.adapters import (
    InMemoryPortfolioView,
    InMemoryRiskPolicyRepository,
    InMemoryTradingHaltRepository,
)
from pytradekit.risk.application import EvaluateOrderRisk, OrderRiskRequest, TriggerTradingHalt
from pytradekit.risk.domain import RiskDecision, RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.risk.domain.rules import MaxOrderSize
from pytradekit.shared import Currency, InstrumentId, Money, Price, Quantity
from pytradekit.testing import FakeClock

USD = Currency("USD")
NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def _service(
    *,
    cash: str = "50000",
) -> tuple[
    EvaluateOrderRisk,
    AccountId,
    InMemoryRiskPolicyRepository,
    InMemoryTradingHaltRepository,
]:
    account_id = AccountId.new()
    amount = Money(Decimal(cash), USD)
    snapshot = PortfolioSnapshot(
        account_id=account_id,
        as_of=NOW,
        base_currency=USD,
        cash=(
            Balance(
                account_id=account_id,
                currency=USD,
                cash=amount,
                updated_at=NOW,
            ),
        ),
        positions=(),
        nav=amount,
        gross_exposure=Money.zero(USD),
        net_exposure=Money.zero(USD),
        realized_pnl=Money.zero(USD),
        unrealized_pnl=Money.zero(USD),
        leverage=Decimal("0"),
    )
    portfolio = InMemoryPortfolioView()
    portfolio.set_snapshot(snapshot)
    policies = InMemoryRiskPolicyRepository()
    halts = InMemoryTradingHaltRepository()
    service = EvaluateOrderRisk(
        policies=policies,
        halts=halts,
        portfolio=portfolio,
        clock=FakeClock(NOW),
    )
    return service, account_id, policies, halts


def test_risk_evaluates_projected_order_and_rejects() -> None:
    service, account_id, policies, _ = _service()
    policies.save(
        RiskPolicy(
            id=RiskPolicyId.new(),
            name="global",
            scope=RiskScope.GLOBAL,
            limits=(MaxOrderSize(Money(Decimal("10000"), USD)),),
            enabled=True,
            version=1,
        )
    )

    result = service.execute(
        OrderRiskRequest(
            account_id=account_id,
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("100")),
            reference_price=Price(Decimal("120"), USD),
        )
    )

    assert result.decision is RiskDecision.REJECT
    assert result.violations[0].code == "MAX_ORDER_SIZE_EXCEEDED"
    assert result.projected is not None
    assert result.projected.order_notional == Money(Decimal("12000"), USD)


def test_missing_market_price_fails_safe() -> None:
    service, account_id, policies, _ = _service()
    policies.save(
        RiskPolicy(
            id=RiskPolicyId.new(),
            name="global",
            scope=RiskScope.GLOBAL,
            limits=(),
            enabled=True,
            version=1,
        )
    )

    result = service.execute(
        OrderRiskRequest(
            account_id=account_id,
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("1")),
        )
    )

    assert result.decision is RiskDecision.REJECT
    assert result.issues == ("REFERENCE_PRICE_UNAVAILABLE",)


def test_global_halt_rejects_risk_increase() -> None:
    service, account_id, policies, halts = _service()
    policies.save(
        RiskPolicy(
            id=RiskPolicyId.new(),
            name="global",
            scope=RiskScope.GLOBAL,
            limits=(),
            enabled=True,
            version=1,
        )
    )
    TriggerTradingHalt(
        repository=halts,
        clock=FakeClock(NOW),
    ).execute(scope=RiskScope.GLOBAL, scope_id=None, reason="manual")

    result = service.execute(
        OrderRiskRequest(
            account_id=account_id,
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("1")),
            reference_price=Price(Decimal("100"), USD),
        )
    )

    assert result.decision is RiskDecision.REJECT
    assert result.issues == ("TRADING_HALTED",)
