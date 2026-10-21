"""Hypothesis strategies for PyTradeKit financial domain values."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from pytradekit.shared import Currency, Money, Price, Quantity


def finite_decimals() -> SearchStrategy[Decimal]:
    """Generate bounded finite Decimal values suitable for general finance tests."""
    return st.decimals(
        min_value=Decimal("-1000000"),
        max_value=Decimal("1000000"),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )


def currencies() -> SearchStrategy[Currency]:
    """Generate a small canonical set of fiat currencies."""
    return st.sampled_from(
        [
            Currency("USD"),
            Currency("EUR"),
            Currency("GBP"),
            Currency("CHF"),
            Currency("JPY"),
            Currency("CAD"),
            Currency("AUD"),
        ]
    )


def money_values() -> SearchStrategy[Money]:
    """Generate finite Money values."""
    return st.builds(Money, amount=finite_decimals(), currency=currencies())


def quantities() -> SearchStrategy[Quantity]:
    """Generate non-negative finite quantities."""
    values = st.decimals(
        min_value=Decimal("0"),
        max_value=Decimal("1000000"),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )
    return st.builds(Quantity, value=values)


def prices() -> SearchStrategy[Price]:
    """Generate strictly positive finite prices."""
    values = st.decimals(
        min_value=Decimal("0.0001"),
        max_value=Decimal("1000000"),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )
    return st.builds(Price, value=values, currency=currencies())
