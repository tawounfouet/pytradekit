"""Unit tests for the Order aggregate."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.orders import (
    ExecutionCertainty,
    InvalidOrderTransitionError,
    Order,
    OrderId,
    OrderSide,
    OrderStatus,
    TimeInForce,
)
from pytradekit.shared import (
    CorrelationId,
    InstrumentId,
    InvariantViolationError,
    Quantity,
)

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def _market_order(*, quantity: str = "10") -> Order:
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
    return order


def test_order_happy_path_reaches_filled() -> None:
    order = _market_order()
    order.accept(external_order_id="broker-1", occurred_at=NOW)

    assert order.apply_fill(
        fill_id="fill-1",
        fill_quantity=Quantity(Decimal("4")),
        occurred_at=NOW,
        external_order_id="broker-1",
    )
    assert order.status is OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == Quantity(Decimal("4"))

    assert order.apply_fill(
        fill_id="fill-2",
        fill_quantity=Quantity(Decimal("6")),
        occurred_at=NOW,
        external_order_id="broker-1",
    )
    assert order.status is OrderStatus.FILLED
    assert order.remaining_quantity == Quantity(Decimal("0"))


def test_duplicate_fill_has_one_economic_effect() -> None:
    order = _market_order()
    order.accept(external_order_id="broker-1", occurred_at=NOW)

    first = order.apply_fill(
        fill_id="fill-1",
        fill_quantity=Quantity(Decimal("4")),
        occurred_at=NOW,
    )
    version_after_first = order.version
    duplicate = order.apply_fill(
        fill_id="fill-1",
        fill_quantity=Quantity(Decimal("4")),
        occurred_at=NOW,
    )

    assert first is True
    assert duplicate is False
    assert order.filled_quantity == Quantity(Decimal("4"))
    assert order.version == version_after_first


def test_overfill_is_rejected() -> None:
    order = _market_order(quantity="5")
    order.accept(external_order_id="broker-1", occurred_at=NOW)

    with pytest.raises(InvariantViolationError):
        order.apply_fill(
            fill_id="fill-1",
            fill_quantity=Quantity(Decimal("6")),
            occurred_at=NOW,
        )


def test_terminal_state_does_not_regress_on_late_acceptance() -> None:
    order = _market_order(quantity="5")
    order.accept(external_order_id="broker-1", occurred_at=NOW)
    order.apply_fill(
        fill_id="fill-1",
        fill_quantity=Quantity(Decimal("5")),
        occurred_at=NOW,
    )
    version = order.version

    changed = order.accept(external_order_id="broker-1", occurred_at=NOW)

    assert changed is False
    assert order.status is OrderStatus.FILLED
    assert order.version == version


def test_timeout_marks_uncertainty_without_failure() -> None:
    order = _market_order()

    order.mark_submission_uncertain(occurred_at=NOW)

    assert order.status is OrderStatus.SUBMITTED
    assert order.execution_certainty is ExecutionCertainty.UNCERTAIN


def test_cancel_fill_race_preserves_fill_then_allows_cancel_confirmation() -> None:
    order = _market_order()
    order.accept(external_order_id="broker-1", occurred_at=NOW)
    order.request_cancel(occurred_at=NOW)

    order.apply_fill(
        fill_id="fill-1",
        fill_quantity=Quantity(Decimal("4")),
        occurred_at=NOW,
    )

    assert order.status is OrderStatus.PARTIALLY_FILLED
    assert order.cancel_requested is True

    assert order.confirm_cancel(occurred_at=NOW) is True
    assert order.status is OrderStatus.CANCELLED
    assert order.filled_quantity == Quantity(Decimal("4"))


def test_invalid_transition_is_rejected() -> None:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )

    with pytest.raises(InvalidOrderTransitionError):
        order.mark_submitted(occurred_at=NOW)
