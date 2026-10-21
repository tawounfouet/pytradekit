"""Unit tests for InstrumentMapping."""

import pytest

from pytradekit.reference import InstrumentMapping
from pytradekit.shared import DomainValidationError, InstrumentId


def test_instrument_mapping_preserves_internal_identity() -> None:
    instrument_id = InstrumentId.new()

    mapping = InstrumentMapping(
        instrument_id=instrument_id,
        provider="alpaca",
        external_symbol="AAPL",
        external_id="provider-123",
    )

    assert mapping.instrument_id == instrument_id
    assert mapping.provider == "alpaca"
    assert mapping.external_symbol == "AAPL"
    assert mapping.external_id == "provider-123"


@pytest.mark.parametrize("provider", ["", "   "])
def test_instrument_mapping_requires_provider(provider: str) -> None:
    with pytest.raises(DomainValidationError, match="provider"):
        InstrumentMapping(
            instrument_id=InstrumentId.new(),
            provider=provider,
            external_symbol="AAPL",
        )


@pytest.mark.parametrize("external_symbol", ["", "   "])
def test_instrument_mapping_requires_external_symbol(
    external_symbol: str,
) -> None:
    with pytest.raises(DomainValidationError, match="external_symbol"):
        InstrumentMapping(
            instrument_id=InstrumentId.new(),
            provider="alpaca",
            external_symbol=external_symbol,
        )
