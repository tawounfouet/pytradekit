"""Position accounting unit tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain import AccountId, Position, PositionSide
from pytradekit.shared import Currency, InstrumentId, Price, Quantity

USD = Currency("USD")
T0 = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def _position() -> Position:
    return Position.flat(
        account_id=AccountId.new(),
        instrument_id=InstrumentId.new(),
        currency=USD,
        occurred_at=T0,
    )


def test_long_lifecycle_and_realized_pnl() -> None:
    position = _position()
    position.apply_fill(
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("10")),
        price=Price(Decimal("100"), USD),
        occurred_at=T0,
    )
    position.apply_fill(
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("10")),
        price=Price(Decimal("120"), USD),
        occurred_at=T0 + timedelta(seconds=1),
    )

    assert position.quantity == Decimal("20")
    assert position.average_price == Price(Decimal("110"), USD)
    assert position.side is PositionSide.LONG

    position.apply_fill(
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("5")),
        price=Price(Decimal("130"), USD),
        occurred_at=T0 + timedelta(seconds=2),
    )

    assert position.quantity == Decimal("15")
    assert position.average_price == Price(Decimal("110"), USD)
    assert position.realized_pnl.amount == Decimal("100")

    position.apply_fill(
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("15")),
        price=Price(Decimal("100"), USD),
        occurred_at=T0 + timedelta(seconds=3),
    )

    assert position.quantity == 0
    assert position.average_price is None
    assert position.side is PositionSide.FLAT
    assert position.realized_pnl.amount == Decimal("-50")


def test_position_flip_long_to_short_and_back_to_long() -> None:
    position = _position()
    position.apply_fill(
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("10")),
        price=Price(Decimal("100"), USD),
        occurred_at=T0,
    )
    position.apply_fill(
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("15")),
        price=Price(Decimal("90"), USD),
        occurred_at=T0 + timedelta(seconds=1),
    )

    assert position.quantity == Decimal("-5")
    assert position.average_price == Price(Decimal("90"), USD)
    assert position.side is PositionSide.SHORT
    assert position.realized_pnl.amount == Decimal("-100")

    position.apply_fill(
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("8")),
        price=Price(Decimal("80"), USD),
        occurred_at=T0 + timedelta(seconds=2),
    )

    assert position.quantity == Decimal("3")
    assert position.average_price == Price(Decimal("80"), USD)
    assert position.side is PositionSide.LONG
    assert position.realized_pnl.amount == Decimal("-50")
