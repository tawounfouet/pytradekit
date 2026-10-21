"""Unit tests for ContractSpecification."""

from decimal import Decimal

import pytest

from pytradekit.reference import ContractSpecification
from pytradekit.shared import Currency, DomainValidationError, Price, Quantity


@pytest.mark.parametrize("tick_size", [Decimal("0"), Decimal("-0.01")])
def test_contract_specification_rejects_non_positive_tick(
    tick_size: Decimal,
) -> None:
    with pytest.raises(DomainValidationError, match="tick_size"):
        ContractSpecification(tick_size=tick_size)


@pytest.mark.parametrize("quantity_step", [Decimal("0"), Decimal("-1")])
def test_contract_specification_rejects_non_positive_step(
    quantity_step: Decimal,
) -> None:
    with pytest.raises(DomainValidationError, match="quantity_step"):
        ContractSpecification(quantity_step=quantity_step)


def test_contract_specification_rejects_min_greater_than_max() -> None:
    with pytest.raises(DomainValidationError, match="max_quantity"):
        ContractSpecification(
            min_quantity=Decimal("10"),
            max_quantity=Decimal("5"),
        )


def test_contract_specification_accepts_valid_quantity() -> None:
    specification = ContractSpecification(
        quantity_step=Decimal("0.25"),
        min_quantity=Decimal("0.50"),
        max_quantity=Decimal("10"),
    )

    assert specification.is_valid_quantity(Quantity(Decimal("1.25")))


def test_contract_specification_rejects_quantity_not_aligned_to_step() -> None:
    specification = ContractSpecification(quantity_step=Decimal("0.25"))

    assert not specification.is_valid_quantity(Quantity(Decimal("1.10")))


def test_contract_specification_checks_quantity_bounds() -> None:
    specification = ContractSpecification(
        min_quantity=Decimal("1"),
        max_quantity=Decimal("5"),
    )

    assert not specification.is_valid_quantity(Quantity(Decimal("0.5")))
    assert specification.is_valid_quantity(Quantity(Decimal("3")))
    assert not specification.is_valid_quantity(Quantity(Decimal("6")))


def test_contract_specification_accepts_price_aligned_to_tick() -> None:
    specification = ContractSpecification(tick_size=Decimal("0.05"))

    assert specification.is_valid_price(
        Price(Decimal("192.50"), Currency("USD"))
    )


def test_contract_specification_rejects_price_not_aligned_to_tick() -> None:
    specification = ContractSpecification(tick_size=Decimal("0.05"))

    assert not specification.is_valid_price(
        Price(Decimal("192.53"), Currency("USD"))
    )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("min_quantity", Decimal("-0.01")),
        ("max_quantity", Decimal("-0.01")),
        ("min_notional", Decimal("-0.01")),
    ],
)
def test_contract_specification_rejects_negative_limits(
    field_name: str,
    value: Decimal,
) -> None:
    with pytest.raises(DomainValidationError):
        ContractSpecification(**{field_name: value})
