from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.market_data import Bar, MarketDataEvent
from pytradekit.shared import Currency, DomainValidationError, InstrumentId, Price


def test_bar_enforces_ohlc_invariants() -> None:
    usd = Currency("USD")
    instrument_id = InstrumentId.new()
    with pytest.raises(DomainValidationError):
        Bar(
            instrument_id=instrument_id,
            interval="1d",
            open=Price(Decimal("100"), usd),
            high=Price(Decimal("99"), usd),
            low=Price(Decimal("98"), usd),
            close=Price(Decimal("100"), usd),
            start_time=datetime(2026, 1, 1, tzinfo=UTC),
            end_time=datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_market_data_event_time_is_bar_end() -> None:
    usd = Currency("USD")
    end = datetime(2026, 1, 2, tzinfo=UTC)
    bar = Bar(
        instrument_id=InstrumentId.new(),
        interval="1d",
        open=Price(Decimal("100"), usd),
        high=Price(Decimal("101"), usd),
        low=Price(Decimal("99"), usd),
        close=Price(Decimal("100"), usd),
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        end_time=end,
    )
    assert MarketDataEvent(bar=bar).event_time == end
