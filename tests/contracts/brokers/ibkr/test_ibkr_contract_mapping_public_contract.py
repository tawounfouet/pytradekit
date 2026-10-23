"""Public contract for IBKR Contract and instrument mapping."""

from decimal import Decimal

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRInstrumentMappingResult,
    IBKRPriceIncrementMode,
    IBKRSecurityType,
    map_ibkr_stock_contract,
)
from pytradekit.shared import InstrumentId


def test_ibkr_contract_mapping_surface_is_importable() -> None:
    details = IBKRContractDetailsRecord(
        contract=IBKRContractRecord(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
            security_type=IBKRSecurityType.STOCK,
            exchange="SMART",
            primary_exchange="NASDAQ",
            currency="USD",
            local_symbol="AAPL",
        ),
        min_tick=Decimal("0.01"),
        min_size=Decimal("1"),
        size_increment=Decimal("1"),
    )

    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    assert isinstance(result, IBKRInstrumentMappingResult)
    assert result.price_increment_mode is IBKRPriceIncrementMode.STATIC
