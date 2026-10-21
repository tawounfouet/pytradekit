"""Unit tests for InstrumentBuilder."""

from pytradekit.reference import AssetClass
from pytradekit.shared import Currency, InstrumentId
from pytradekit.testing import InstrumentBuilder


def test_equity_builder_creates_canonical_equity() -> None:
    instrument = InstrumentBuilder.equity(symbol="MSFT", currency="USD")

    assert isinstance(instrument.id, InstrumentId)
    assert instrument.symbol == "MSFT"
    assert instrument.asset_class is AssetClass.EQUITY
    assert instrument.quote_currency == Currency("USD")


def test_equity_builder_preserves_explicit_instrument_id() -> None:
    instrument_id = InstrumentId.new()

    instrument = InstrumentBuilder.equity(
        instrument_id=instrument_id,
        symbol="AAPL",
        currency="USD",
    )

    assert instrument.id == instrument_id
