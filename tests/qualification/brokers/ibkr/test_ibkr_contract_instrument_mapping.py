"""LOT-05.2 qualification for IBKR Contract and instrument mapping."""

from decimal import Decimal

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRPriceIncrementMode,
    IBKRSecurityType,
    map_ibkr_stock_contract,
)
from pytradekit.reference.domain import AssetClass
from pytradekit.shared import InstrumentId


def test_lot05_2_maps_stable_contract_identity_without_sdk_types() -> None:
    details = IBKRContractDetailsRecord(
        contract=IBKRContractRecord(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
            security_type=IBKRSecurityType.STOCK,
            exchange="SMART",
            primary_exchange="NASDAQ",
            currency="USD",
            local_symbol="AAPL",
            trading_class="NMS",
        ),
        min_tick=Decimal("0.01"),
        min_size=Decimal("0.0001"),
        size_increment=Decimal("0.0001"),
        valid_exchanges=("SMART", "NASDAQ"),
        market_rule_ids=(26, 26),
        time_zone_id="US/Eastern",
    )

    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    assert result.identity.external_id == "265598"
    assert result.instrument.asset_class is AssetClass.EQUITY
    assert result.primary_exchange == "NASDAQ"
    assert result.routing_exchange == "SMART"


def test_lot05_2_preserves_dynamic_tick_semantics_in_provider_layer() -> None:
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
        valid_exchanges=("SMART",),
        market_rule_ids=(26,),
    )

    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    assert result.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE
    assert result.reported_min_tick == Decimal("0.01")
    assert result.specification.tick_size is None
