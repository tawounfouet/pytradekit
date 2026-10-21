"""Property tests for reusable finance strategies."""

from decimal import Decimal

from hypothesis import given

from pytradekit.shared import Currency, Money, Price, Quantity
from pytradekit.testing.strategies import (
    currencies,
    finite_decimals,
    money_values,
    prices,
    quantities,
)


@given(finite_decimals())
def test_finite_decimals_generate_only_finite_values(value: Decimal) -> None:
    assert value.is_finite()


@given(currencies())
def test_currencies_generate_canonical_currency_values(currency: Currency) -> None:
    assert len(currency.code) == 3
    assert currency.code.isupper()


@given(money_values())
def test_money_strategy_generates_valid_money(money: Money) -> None:
    assert money.amount.is_finite()
    assert isinstance(money.currency, Currency)


@given(quantities())
def test_quantity_strategy_generates_non_negative_values(quantity: Quantity) -> None:
    assert quantity.value.is_finite()
    assert quantity.value >= 0


@given(prices())
def test_price_strategy_generates_strictly_positive_values(price: Price) -> None:
    assert price.value.is_finite()
    assert price.value > 0
