"""Testing builders for canonical instruments."""

from __future__ import annotations

from pytradekit.reference import AssetClass, Instrument
from pytradekit.shared import Currency, InstrumentId


class InstrumentBuilder:
    """Testing-only factory for common instrument fixtures."""

    @staticmethod
    def equity(
        *,
        symbol: str = "AAPL",
        currency: str = "USD",
        instrument_id: InstrumentId | None = None,
    ) -> Instrument:
        """Build a canonical equity instrument."""
        return Instrument(
            id=instrument_id or InstrumentId.new(),
            symbol=symbol,
            asset_class=AssetClass.EQUITY,
            quote_currency=Currency(currency),
        )
