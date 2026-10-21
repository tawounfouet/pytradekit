"""Canonical provider-independent instrument model."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.reference.domain.asset_class import AssetClass
from pytradekit.shared import Currency, DomainValidationError, InstrumentId


@dataclass(frozen=True, slots=True)
class Instrument:
    """Canonical instrument identity independent from provider identifiers."""

    id: InstrumentId
    symbol: str
    asset_class: AssetClass
    quote_currency: Currency

    def __post_init__(self) -> None:
        """Validate the canonical instrument representation."""
        raw_id: object = self.id
        raw_symbol: object = self.symbol
        raw_asset_class: object = self.asset_class
        raw_quote_currency: object = self.quote_currency

        if not isinstance(raw_id, InstrumentId):
            raise DomainValidationError("Instrument id must be an InstrumentId.")

        if not isinstance(raw_symbol, str) or not raw_symbol.strip():
            raise DomainValidationError("Instrument symbol must be a non-empty string.")

        if not isinstance(raw_asset_class, AssetClass):
            raise DomainValidationError("Instrument asset_class must be an AssetClass.")

        if not isinstance(raw_quote_currency, Currency):
            raise DomainValidationError(
                "Instrument quote_currency must be a Currency."
            )
