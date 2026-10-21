"""ApplyFillToPortfolio unit tests."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.execution import Fill, FillId
from pytradekit.orders.domain import OrderId, OrderSide
from pytradekit.portfolio.adapters import (
    InMemoryBalanceRepository,
    InMemoryPositionRepository,
    InMemoryProcessedFillRegistry,
)
from pytradekit.portfolio.application import ApplyFillToPortfolio
from pytradekit.portfolio.domain import AccountId, Balance
from pytradekit.shared import Currency, InstrumentId, Money, Price, Quantity

USD = Currency("USD")
NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def test_fill_updates_position_cash_and_fee_once() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    positions = InMemoryPositionRepository()
    balances = InMemoryBalanceRepository()
    processed = InMemoryProcessedFillRegistry()
    balances.save(
        Balance(
            account_id=account_id,
            currency=USD,
            cash=Money(Decimal("20000"), USD),
            updated_at=NOW,
        )
    )
    service = ApplyFillToPortfolio(
        positions=positions,
        balances=balances,
        processed_fills=processed,
    )
    fill = Fill(
        id=FillId.new(),
        order_id=OrderId.new(),
        quantity=Quantity(Decimal("10")),
        price=Price(Decimal("100"), USD),
        occurred_at=NOW,
        external_fill_id="fill-1",
        fee=Money(Decimal("2"), USD),
    )

    first = service.execute(
        fill,
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
    )
    second = service.execute(
        fill,
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
    )

    assert first.applied is True
    assert first.position.quantity == Decimal("10")
    assert first.balance.cash == Money(Decimal("18998"), USD)
    assert second.applied is False
    assert second.position.quantity == Decimal("10")
    assert second.balance.cash == Money(Decimal("18998"), USD)


def test_sell_fill_increases_cash_and_can_open_short() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    positions = InMemoryPositionRepository()
    balances = InMemoryBalanceRepository()
    processed = InMemoryProcessedFillRegistry()
    balances.save(
        Balance(
            account_id=account_id,
            currency=USD,
            cash=Money(Decimal("1000"), USD),
            updated_at=NOW,
        )
    )
    service = ApplyFillToPortfolio(
        positions=positions,
        balances=balances,
        processed_fills=processed,
    )
    fill = Fill(
        id=FillId.new(),
        order_id=OrderId.new(),
        quantity=Quantity(Decimal("2")),
        price=Price(Decimal("50"), USD),
        occurred_at=NOW,
    )

    result = service.execute(
        fill,
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.SELL,
    )

    assert result.position.quantity == Decimal("-2")
    assert result.balance.cash == Money(Decimal("1100"), USD)
