"""Property tests for portfolio accounting invariants."""

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain import AccountId, Position
from pytradekit.shared import Currency, InstrumentId, Price, Quantity

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
USD = Currency("USD")
PRICE = Price(Decimal("100"), USD)
FILL_SEQUENCE = st.lists(
    st.tuples(
        st.sampled_from([OrderSide.BUY, OrderSide.SELL]),
        st.integers(min_value=1, max_value=100),
    ),
    min_size=1,
    max_size=30,
)


def _flat() -> Position:
    return Position.flat(
        account_id=AccountId.new(),
        instrument_id=InstrumentId.new(),
        currency=USD,
        occurred_at=NOW,
    )


@given(FILL_SEQUENCE)
def test_signed_quantity_equals_buy_minus_sell(
    fills: list[tuple[OrderSide, int]],
) -> None:
    position = _flat()
    expected = Decimal("0")

    for side, raw_quantity in fills:
        quantity = Quantity(Decimal(raw_quantity))
        position.apply_fill(
            side=side,
            quantity=quantity,
            price=PRICE,
            occurred_at=NOW,
        )
        if side is OrderSide.BUY:
            expected += quantity.value
        else:
            expected -= quantity.value

    assert position.quantity == expected
    if expected == 0:
        assert position.average_price is None
    else:
        assert position.average_price is not None


@given(st.integers(min_value=1, max_value=1000))
def test_full_close_is_flat_with_no_average_price(raw_quantity: int) -> None:
    position = _flat()
    quantity = Quantity(Decimal(raw_quantity))
    position.apply_fill(
        side=OrderSide.BUY,
        quantity=quantity,
        price=PRICE,
        occurred_at=NOW,
    )
    position.apply_fill(
        side=OrderSide.SELL,
        quantity=quantity,
        price=PRICE,
        occurred_at=NOW,
    )

    assert position.quantity == 0
    assert position.average_price is None
