"""Property tests for Order aggregate fill invariants."""

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.orders import Order, OrderId, OrderSide, OrderStatus, TimeInForce
from pytradekit.shared import CorrelationId, InstrumentId, Quantity

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
POSITIVE = st.integers(min_value=1, max_value=1000)


def _accepted_order(quantity: int) -> Order:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal(quantity)),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    order.accept(external_order_id="broker-1", occurred_at=NOW)
    return order


@given(POSITIVE, POSITIVE)
def test_duplicate_fill_changes_quantity_once(total: int, raw_fill: int) -> None:
    fill_value = min(total, raw_fill)
    order = _accepted_order(total)
    quantity = Quantity(Decimal(fill_value))

    order.apply_fill(fill_id="stable-fill", fill_quantity=quantity, occurred_at=NOW)
    first_quantity = order.filled_quantity
    order.apply_fill(fill_id="stable-fill", fill_quantity=quantity, occurred_at=NOW)

    assert order.filled_quantity == first_quantity
    assert order.filled_quantity.value <= order.quantity.value


@given(POSITIVE)
def test_full_fill_always_implies_filled_status(total: int) -> None:
    order = _accepted_order(total)

    order.apply_fill(
        fill_id="final-fill",
        fill_quantity=Quantity(Decimal(total)),
        occurred_at=NOW,
    )

    assert order.filled_quantity == order.quantity
    assert order.status is OrderStatus.FILLED
