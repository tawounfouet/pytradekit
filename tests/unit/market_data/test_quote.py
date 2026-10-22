"""Unit tests for canonical level-1 quotes."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.market_data import Quote
from pytradekit.shared import (
    Currency,
    DomainValidationError,
    InstrumentId,
    Price,
    Quantity,
)


def test_quote_accepts_two_sided_provider_neutral_market_data() -> None:
    usd = Currency("USD")
    quote = Quote(
        instrument_id=InstrumentId.new(),
        bid_price=Price(Decimal("191.24"), usd),
        bid_size=Quantity(Decimal("10")),
        ask_price=Price(Decimal("191.25"), usd),
        ask_size=Quantity(Decimal("8")),
        occurred_at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
    )

    assert quote.bid_price is not None
    assert quote.bid_price.value == Decimal("191.24")
    assert quote.ask_price is not None
    assert quote.ask_price.value == Decimal("191.25")


def test_quote_allows_one_sided_market_but_not_zero_information() -> None:
    usd = Currency("USD")
    quote = Quote(
        instrument_id=InstrumentId.new(),
        bid_price=None,
        bid_size=Quantity(Decimal("0")),
        ask_price=Price(Decimal("191.25"), usd),
        ask_size=Quantity(Decimal("8")),
        occurred_at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
    )

    assert quote.bid_price is None

    with pytest.raises(DomainValidationError, match="at least one priced side"):
        Quote(
            instrument_id=InstrumentId.new(),
            bid_price=None,
            bid_size=Quantity(Decimal("0")),
            ask_price=None,
            ask_size=Quantity(Decimal("0")),
            occurred_at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
        )
