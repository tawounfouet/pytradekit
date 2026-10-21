"""Provider mapping for canonical instruments."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.shared import DomainValidationError, InstrumentId


@dataclass(frozen=True, slots=True)
class InstrumentMapping:
    """Map a canonical instrument identifier to a provider representation."""

    instrument_id: InstrumentId
    provider: str
    external_symbol: str
    external_id: str | None = None

    def __post_init__(self) -> None:
        """Validate the provider mapping."""
        raw_instrument_id: object = self.instrument_id
        raw_provider: object = self.provider
        raw_external_symbol: object = self.external_symbol
        raw_external_id: object = self.external_id

        if not isinstance(raw_instrument_id, InstrumentId):
            raise DomainValidationError(
                "InstrumentMapping instrument_id must be an InstrumentId."
            )

        if not isinstance(raw_provider, str) or not raw_provider.strip():
            raise DomainValidationError(
                "InstrumentMapping provider must be a non-empty string."
            )

        if not isinstance(raw_external_symbol, str) or not raw_external_symbol.strip():
            raise DomainValidationError(
                "InstrumentMapping external_symbol must be a non-empty string."
            )

        if raw_external_id is not None and not isinstance(raw_external_id, str):
            raise DomainValidationError(
                "InstrumentMapping external_id must be a string or None."
            )
