"""Unit tests for Currency."""

from dataclasses import FrozenInstanceError

import pytest

from pytradekit.shared import Currency
from pytradekit.shared.errors import DomainValidationError


def test_currency_accepts_canonical_code() -> None:
    currency = Currency("EUR")

    assert currency.code == "EUR"
    assert str(currency) == "EUR"


def test_currency_normalizes_whitespace_and_case() -> None:
    currency = Currency(" usd ")

    assert currency.code == "USD"


@pytest.mark.parametrize(
    "code",
    [
        "",
        " ",
        "US",
        "EURO",
        "12A",
        "E-R",
        "€UR",
    ],
)
def test_currency_rejects_invalid_codes(code: str) -> None:
    with pytest.raises(DomainValidationError):
        Currency(code)


def test_currency_is_immutable() -> None:
    currency = Currency("EUR")

    with pytest.raises(FrozenInstanceError):
        setattr(currency, "code", "USD")


def test_currency_has_value_equality_and_hash_semantics() -> None:
    left = Currency("eur")
    right = Currency("EUR")

    assert left == right
    assert hash(left) == hash(right)
    assert {left, right} == {Currency("EUR")}
