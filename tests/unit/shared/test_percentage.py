"""Unit tests for Percentage."""

from decimal import Decimal

import pytest

from pytradekit.shared import Percentage
from pytradekit.shared.errors import DomainValidationError


@pytest.mark.parametrize(
    "value",
    [
        Decimal("0.05"),
        Decimal("-0.20"),
        Decimal("1.50"),
        Decimal("0"),
    ],
)
def test_percentage_accepts_unbounded_finite_ratios(value: Decimal) -> None:
    assert Percentage(value).value == value


def test_percentage_from_percent_round_trip() -> None:
    percentage = Percentage.from_percent(Decimal("5"))

    assert percentage == Percentage(Decimal("0.05"))
    assert percentage.as_percent() == Decimal("5.00")


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_percentage_rejects_non_finite_values(value: Decimal) -> None:
    with pytest.raises(DomainValidationError):
        Percentage(value)
