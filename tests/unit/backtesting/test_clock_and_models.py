from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.backtesting import BacktestClock, FixedBpsSlippage
from pytradekit.orders.domain import OrderSide
from pytradekit.shared import Currency, InvariantViolationError, Price


def test_backtest_clock_is_explicit_and_monotonic() -> None:
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = datetime(2026, 1, 2, tzinfo=UTC)
    clock = BacktestClock(first)
    clock.advance_to(second)
    assert clock.now() == second
    with pytest.raises(InvariantViolationError):
        clock.advance_to(first)


def test_pessimistic_slippage_never_improves_price() -> None:
    usd = Currency("USD")
    price = Price(Decimal("100"), usd)
    model = FixedBpsSlippage(Decimal("10"))
    assert model.apply(price, OrderSide.BUY).value > price.value
    assert model.apply(price, OrderSide.SELL).value < price.value
