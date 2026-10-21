"""Portfolio valuation unit tests."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.adapters import (
    InMemoryBalanceRepository,
    InMemoryPositionRepository,
)
from pytradekit.portfolio.application import BuildPortfolioSnapshot
from pytradekit.portfolio.domain import Account, AccountId, Balance, Position
from pytradekit.shared import Currency, InstrumentId, Money, Price, Quantity
from pytradekit.testing import FakeClock

USD = Currency("USD")
NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def test_snapshot_values_long_and_short_positions() -> None:
    account = Account(id=AccountId.new(), base_currency=USD)
    long_id = InstrumentId.new()
    short_id = InstrumentId.new()
    positions = InMemoryPositionRepository()
    balances = InMemoryBalanceRepository()
    balances.save(
        Balance(
            account_id=account.id,
            currency=USD,
            cash=Money(Decimal("10000"), USD),
            updated_at=NOW,
        )
    )

    long = Position.flat(
        account_id=account.id,
        instrument_id=long_id,
        currency=USD,
        occurred_at=NOW,
    )
    long.apply_fill(
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("10")),
        price=Price(Decimal("100"), USD),
        occurred_at=NOW,
    )
    short = Position.flat(
        account_id=account.id,
        instrument_id=short_id,
        currency=USD,
        occurred_at=NOW,
    )
    short.apply_fill(
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("5")),
        price=Price(Decimal("200"), USD),
        occurred_at=NOW,
    )
    positions.save(long)
    positions.save(short)

    snapshot = BuildPortfolioSnapshot(
        positions=positions,
        balances=balances,
        clock=FakeClock(NOW),
    ).execute(
        account,
        prices={
            long_id: Price(Decimal("110"), USD),
            short_id: Price(Decimal("180"), USD),
        },
    )

    assert snapshot.nav == Money(Decimal("10200"), USD)
    assert snapshot.gross_exposure == Money(Decimal("2000"), USD)
    assert snapshot.net_exposure == Money(Decimal("200"), USD)
    assert snapshot.unrealized_pnl == Money(Decimal("200"), USD)
    assert snapshot.leverage == Decimal("2000") / Decimal("10200")
