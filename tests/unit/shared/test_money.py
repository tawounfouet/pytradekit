"""Unit tests for Money."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from pytradekit.shared import Currency, Money
from pytradekit.shared.errors import DomainValidationError, InvariantViolationError


def test_money_accepts_finite_decimal_amount() -> None:
    money = Money(Decimal("125.42"), Currency("EUR"))

    assert money.amount == Decimal("125.42")
    assert money.currency == Currency("EUR")
    assert str(money) == "Money(125.42 EUR)"


def test_money_zero_preserves_currency() -> None:
    money = Money.zero(Currency("USD"))

    assert money == Money(Decimal("0"), Currency("USD"))


def test_money_adds_same_currency() -> None:
    left = Money(Decimal("10.25"), Currency("EUR"))
    right = Money(Decimal("2.75"), Currency("EUR"))

    assert left + right == Money(Decimal("13.00"), Currency("EUR"))


def test_money_subtracts_same_currency() -> None:
    left = Money(Decimal("10.25"), Currency("EUR"))
    right = Money(Decimal("2.75"), Currency("EUR"))

    assert left - right == Money(Decimal("7.50"), Currency("EUR"))


def test_money_rejects_currency_mismatch() -> None:
    eur = Money(Decimal("10"), Currency("EUR"))
    usd = Money(Decimal("10"), Currency("USD"))

    with pytest.raises(InvariantViolationError, match="matching currencies"):
        _ = eur + usd


def test_money_supports_unary_minus() -> None:
    money = Money(Decimal("10.25"), Currency("EUR"))

    assert -money == Money(Decimal("-10.25"), Currency("EUR"))


def test_money_supports_decimal_scalar_multiplication() -> None:
    money = Money(Decimal("10.25"), Currency("EUR"))

    assert money * Decimal("2") == Money(Decimal("20.50"), Currency("EUR"))


def test_money_supports_decimal_scalar_division() -> None:
    money = Money(Decimal("10.50"), Currency("EUR"))

    assert money / Decimal("2") == Money(Decimal("5.25"), Currency("EUR"))


def test_money_rejects_zero_divisor() -> None:
    money = Money(Decimal("10"), Currency("EUR"))

    with pytest.raises(DomainValidationError, match="must not be zero"):
        _ = money / Decimal("0")


def test_money_comparison_requires_same_currency() -> None:
    eur = Money(Decimal("10"), Currency("EUR"))
    usd = Money(Decimal("20"), Currency("USD"))

    with pytest.raises(InvariantViolationError, match="matching currencies"):
        _ = eur < usd


def test_money_orders_values_in_same_currency() -> None:
    lower = Money(Decimal("10"), Currency("EUR"))
    higher = Money(Decimal("20"), Currency("EUR"))

    assert lower < higher
    assert lower <= higher
    assert higher > lower
    assert higher >= lower


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_money_rejects_non_finite_amount(amount: Decimal) -> None:
    with pytest.raises(DomainValidationError, match="must be finite"):
        Money(amount, Currency("EUR"))


def test_money_is_immutable() -> None:
    money = Money(Decimal("10"), Currency("EUR"))

    with pytest.raises(FrozenInstanceError):
        money.__setattr__("amount", Decimal("20"))
