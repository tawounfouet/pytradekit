"""P0 risk rule unit tests."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderSide, OrderType
from pytradekit.portfolio.domain import AccountId, Balance, PortfolioSnapshot
from pytradekit.risk.domain import RiskContext, RiskOrder, RiskScope
from pytradekit.risk.domain.projected_portfolio import project_portfolio
from pytradekit.risk.domain.rules import (
    DailyLoss,
    MaxGrossExposure,
    MaxLeverage,
    MaxOrderSize,
    MaxPositionSize,
)
from pytradekit.shared import Currency, InstrumentId, Money, Price, Quantity

USD = Currency("USD")
NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def _snapshot(nav_amount: str = "50000") -> PortfolioSnapshot:
    account_id = AccountId.new()
    nav = Money(Decimal(nav_amount), USD)
    return PortfolioSnapshot(
        account_id=account_id,
        as_of=NOW,
        base_currency=USD,
        cash=(
            Balance(
                account_id=account_id,
                currency=USD,
                cash=nav,
                updated_at=NOW,
            ),
        ),
        positions=(),
        nav=nav,
        gross_exposure=Money.zero(USD),
        net_exposure=Money.zero(USD),
        realized_pnl=Money.zero(USD),
        unrealized_pnl=Money.zero(USD),
        leverage=Decimal("0"),
    )


def _context(*, quantity: str, price: str, nav_amount: str = "50000") -> RiskContext:
    current = _snapshot(nav_amount)
    instrument_id = InstrumentId.new()
    reference_price = Price(Decimal(price), USD)
    order = RiskOrder(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal(quantity)),
        reference_price=reference_price,
    )
    projected = project_portfolio(
        current,
        instrument_id=instrument_id,
        side=order.side,
        quantity=order.quantity,
        reference_price=reference_price,
    )
    return RiskContext(
        current=current,
        projected=projected,
        order=order,
        evaluated_at=NOW,
        scope=RiskScope.GLOBAL,
    )


def test_max_order_size_boundaries() -> None:
    below = _context(quantity="50", price="100")
    equal = _context(quantity="100", price="100")
    above = _context(quantity="101", price="100")
    rule = MaxOrderSize(max_notional=Money(Decimal("10000"), USD))

    assert rule.evaluate(below) is None
    assert rule.evaluate(equal) is None
    assert rule.evaluate(above).code == "MAX_ORDER_SIZE_EXCEEDED"  # type: ignore[union-attr]


def test_max_position_gross_exposure_and_leverage() -> None:
    context = _context(quantity="1000", price="120")

    position_violation = MaxPositionSize(max_quantity=Decimal("900")).evaluate(context)
    exposure_violation = MaxGrossExposure(Money(Decimal("100000"), USD)).evaluate(context)
    leverage_violation = MaxLeverage(Decimal("2.0")).evaluate(context)

    assert position_violation is not None
    assert position_violation.code == "MAX_POSITION_SIZE_EXCEEDED"
    assert exposure_violation is not None
    assert exposure_violation.code == "MAX_GROSS_EXPOSURE_EXCEEDED"
    assert leverage_violation is not None
    assert leverage_violation.code == "MAX_LEVERAGE_EXCEEDED"


def test_daily_loss_halts_at_threshold() -> None:
    context = _context(quantity="1", price="100", nav_amount="94000")
    context = RiskContext(
        current=context.current,
        projected=context.projected,
        order=context.order,
        evaluated_at=context.evaluated_at,
        scope=context.scope,
        start_of_day_nav=Money(Decimal("100000"), USD),
    )
    violation = DailyLoss(Decimal("0.05")).evaluate(context)

    assert violation is not None
    assert violation.code == "MAX_DAILY_LOSS_EXCEEDED"
