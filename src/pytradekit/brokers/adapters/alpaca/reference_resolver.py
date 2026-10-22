"""Static Alpaca instrument mapping resolver for the 0.5 PAPER runtime."""

from __future__ import annotations

from collections.abc import Iterable

from pytradekit.brokers import ProviderProtocolError
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.shared import InstrumentId

from .contract import ALPACA_PROVIDER_KEY


class StaticAlpacaReferenceResolver:
    """Resolve canonical and provider instrument identities from immutable mappings."""

    def __init__(self, mappings: Iterable[InstrumentMapping]) -> None:
        self._by_instrument: dict[InstrumentId, InstrumentMapping] = {}
        self._by_external_id: dict[str, InstrumentMapping] = {}
        self._by_symbol: dict[str, InstrumentMapping] = {}

        for mapping in mappings:
            self._add(mapping)

        if not self._by_instrument:
            raise ProviderProtocolError(
                "Alpaca reference resolver requires at least one instrument mapping.",
                provider=ALPACA_PROVIDER_KEY,
                operation="configure_reference",
            )

    def resolve(self, instrument_id: InstrumentId) -> InstrumentMapping | None:
        """Resolve one canonical instrument into its Alpaca mapping."""

        return self._by_instrument.get(instrument_id)

    def resolve_provider(
        self,
        *,
        external_id: str | None,
        external_symbol: str,
    ) -> InstrumentMapping | None:
        """Resolve an Alpaca asset identity back to one canonical instrument."""

        normalized_id = external_id.strip() if isinstance(external_id, str) else ""
        if normalized_id:
            match = self._by_external_id.get(normalized_id)
            if match is not None:
                return match

        normalized_symbol = external_symbol.strip().upper()
        if not normalized_symbol:
            return None
        return self._by_symbol.get(normalized_symbol)

    def _add(self, mapping: InstrumentMapping) -> None:
        if mapping.provider.strip().lower() != ALPACA_PROVIDER_KEY:
            raise ProviderProtocolError(
                "Static Alpaca resolver received a non-Alpaca mapping.",
                provider=ALPACA_PROVIDER_KEY,
                operation="configure_reference",
            )

        if mapping.instrument_id in self._by_instrument:
            raise ProviderProtocolError(
                "Duplicate canonical instrument in Alpaca reference resolver.",
                provider=ALPACA_PROVIDER_KEY,
                operation="configure_reference",
            )

        symbol_key = mapping.external_symbol.strip().upper()
        if symbol_key in self._by_symbol:
            raise ProviderProtocolError(
                "Duplicate Alpaca symbol in reference resolver.",
                provider=ALPACA_PROVIDER_KEY,
                operation="configure_reference",
            )

        external_id = (
            mapping.external_id.strip()
            if isinstance(mapping.external_id, str)
            else ""
        )
        if external_id and external_id in self._by_external_id:
            raise ProviderProtocolError(
                "Duplicate Alpaca external asset ID in reference resolver.",
                provider=ALPACA_PROVIDER_KEY,
                operation="configure_reference",
            )

        self._by_instrument[mapping.instrument_id] = mapping
        self._by_symbol[symbol_key] = mapping
        if external_id:
            self._by_external_id[external_id] = mapping
