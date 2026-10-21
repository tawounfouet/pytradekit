"""Property tests for ContractSpecification."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.reference import ContractSpecification
from pytradekit.shared import Quantity


@given(
    step=st.integers(min_value=1, max_value=1000),
    multiple=st.integers(min_value=0, max_value=1000),
)
def test_quantity_integer_multiple_of_step_is_valid(
    step: int,
    multiple: int,
) -> None:
    decimal_step = Decimal(step) / Decimal("100")
    quantity = Quantity(decimal_step * Decimal(multiple))
    specification = ContractSpecification(quantity_step=decimal_step)

    assert specification.is_valid_quantity(quantity)


@given(
    step=st.integers(min_value=1, max_value=1000),
    multiple=st.integers(min_value=0, max_value=1000),
)
def test_quantity_offset_from_step_is_invalid(
    step: int,
    multiple: int,
) -> None:
    decimal_step = Decimal(step)
    quantity = Quantity(decimal_step * Decimal(multiple) + Decimal("0.5"))
    specification = ContractSpecification(quantity_step=decimal_step)

    assert not specification.is_valid_quantity(quantity)
