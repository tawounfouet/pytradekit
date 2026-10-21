"""Unit tests for Instrument."""

from typing import cast

import pytest

from pytradekit.reference import AssetClass, Instrument
from pytradekit.shared import Currency, DomainValidationError, InstrumentId


def test_instrument_preserves_canonical_identity() -> None:
    instrument_id = InstrumentId.new()

    instrument = Instrument(
        id=instrument_id,
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        quote_currency=Currency("USD"),
    )

    assert instrument.id == instrument_id
    assert instrument.symbol == "AAPL"
    assert instrument.asset_class is AssetClass.EQUITY
    assert instrument.quote_currency == Currency("USD")


@pytest.mark.parametrize("symbol", ["", "   "])
def test_instrument_rejects_empty_symbol(symbol: str) -> None:
    with pytest.raises(DomainValidationError, match="symbol"):
        Instrument(
            id=InstrumentId.new(),
            symbol=symbol,
            asset_class=AssetClass.EQUITY,
            quote_currency=Currency("USD"),
        )


def test_instrument_rejects_missing_canonical_id_type() -> None:
    invalid_id = cast(InstrumentId, "AAPL")

    with pytest.raises(DomainValidationError, match="InstrumentId"):
        Instrument(
            id=invalid_id,
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            quote_currency=Currency("USD"),
        )
