"""Unit tests for static Alpaca reference resolution."""

import pytest

from pytradekit.brokers import ProviderProtocolError
from pytradekit.brokers.adapters.alpaca import StaticAlpacaReferenceResolver
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.shared import InstrumentId


def _mapping(
    *,
    symbol: str = "AAPL",
    external_id: str | None = "asset-aapl",
) -> InstrumentMapping:
    return InstrumentMapping(
        instrument_id=InstrumentId.new(),
        provider="alpaca",
        external_symbol=symbol,
        external_id=external_id,
    )


def test_resolver_maps_canonical_and_provider_identities() -> None:
    mapping = _mapping()
    resolver = StaticAlpacaReferenceResolver([mapping])

    assert resolver.resolve(mapping.instrument_id) == mapping
    assert (
        resolver.resolve_provider(
            external_id="asset-aapl",
            external_symbol="AAPL",
        )
        == mapping
    )
    assert (
        resolver.resolve_provider(
            external_id=None,
            external_symbol="aapl",
        )
        == mapping
    )


def test_resolver_rejects_non_alpaca_mapping() -> None:
    mapping = InstrumentMapping(
        instrument_id=InstrumentId.new(),
        provider="ibkr",
        external_symbol="AAPL",
        external_id="265598",
    )

    with pytest.raises(ProviderProtocolError, match="non-Alpaca"):
        StaticAlpacaReferenceResolver([mapping])


def test_resolver_rejects_duplicate_provider_symbol() -> None:
    first = _mapping(symbol="AAPL", external_id="asset-one")
    second = _mapping(symbol="AAPL", external_id="asset-two")

    with pytest.raises(ProviderProtocolError, match="Duplicate Alpaca symbol"):
        StaticAlpacaReferenceResolver([first, second])
