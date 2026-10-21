"""Property tests for financial value objects."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.shared import Currency, Money, Percentage, Price, Quantity

FINITE_DECIMALS = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=4,
)

NON_NEGATIVE_DECIMALS = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=4,
)

POSITIVE_DECIMALS = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=4,
)


@given(FINITE_DECIMALS, FINITE_DECIMALS)
def test_money_add_subtract_round_trip(left: Decimal, right: Decimal) -> None:
    currency = Currency("EUR")
    a = Money(left, currency)
    b = Money(right, currency)

    assert (a + b) - b == a


@given(POSITIVE_DECIMALS, NON_NEGATIVE_DECIMALS)
def test_price_times_quantity_preserves_notional(
    price_value: Decimal,
    quantity_value: Decimal,
) -> None:
    currency = Currency("USD")
    price = Price(price_value, currency)
    quantity = Quantity(quantity_value)

    notional = price * quantity

    assert notional == Money(price_value * quantity_value, currency)


@given(FINITE_DECIMALS)
def test_percentage_percent_round_trip(value: Decimal) -> None:
    percentage = Percentage(value)

    assert Percentage.from_percent(percentage.as_percent()) == percentage
