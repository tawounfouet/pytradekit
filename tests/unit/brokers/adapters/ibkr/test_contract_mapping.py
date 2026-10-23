"""Unit tests for IBKR Contract and instrument mapping."""

from collections.abc import Callable
from decimal import Decimal

import pytest

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractMappingError,
    IBKRContractRecord,
    IBKRPriceIncrementMode,
    IBKRSecurityType,
    map_ibkr_stock_contract,
)
from pytradekit.reference.domain import AssetClass
from pytradekit.shared import Currency, InstrumentId


def _aapl_details(
    *,
    exchange: str = "SMART",
    currency: str = "USD",
    market_rule_ids: tuple[int | None, ...] = (26, 26),
) -> IBKRContractDetailsRecord:
    return IBKRContractDetailsRecord(
        contract=IBKRContractRecord(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
            security_type=IBKRSecurityType.STOCK,
            exchange=exchange,
            primary_exchange="NASDAQ",
            currency=currency,
            local_symbol="AAPL",
            trading_class="NMS",
        ),
        min_tick=Decimal("0.01"),
        min_size=Decimal("0.0001"),
        size_increment=Decimal("0.0001"),
        suggested_size_increment=Decimal("0.0001"),
        valid_exchanges=("SMART", "NASDAQ"),
        market_rule_ids=market_rule_ids,
        order_types=("MKT", "LMT"),
        time_zone_id="US/Eastern",
        stock_type="COMMON",
    )


def test_market_rule_contract_does_not_fake_static_tick_size() -> None:
    instrument_id = InstrumentId.new()
    result = map_ibkr_stock_contract(
        _aapl_details(),
        instrument_id=instrument_id,
    )

    assert result.identity.external_id == "265598"
    assert result.identity.external_symbol == "AAPL"
    assert result.instrument.id == instrument_id
    assert result.instrument.symbol == "AAPL"
    assert result.instrument.asset_class is AssetClass.EQUITY
    assert result.instrument.quote_currency == Currency("USD")
    assert result.mapping.instrument_id == instrument_id
    assert result.mapping.provider == "ibkr"
    assert result.mapping.external_id == "265598"
    assert result.mapping.external_symbol == "AAPL"
    assert result.specification.tick_size is None
    assert result.specification.quantity_step == Decimal("0.0001")
    assert result.specification.min_quantity == Decimal("0.0001")
    assert result.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE
    assert result.reported_min_tick == Decimal("0.01")
    assert result.market_rule_ids == (26, 26)


def test_static_min_tick_is_used_only_without_market_rules() -> None:
    details = _aapl_details(market_rule_ids=())

    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    assert result.price_increment_mode is IBKRPriceIncrementMode.STATIC
    assert result.specification.tick_size == Decimal("0.01")


def test_missing_min_tick_and_market_rules_leaves_tick_unknown() -> None:
    base = _aapl_details(market_rule_ids=())
    details = IBKRContractDetailsRecord(
        contract=base.contract,
        min_tick=None,
        min_size=base.min_size,
        size_increment=base.size_increment,
        valid_exchanges=base.valid_exchanges,
        order_types=base.order_types,
    )

    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    assert result.price_increment_mode is IBKRPriceIncrementMode.UNKNOWN
    assert result.specification.tick_size is None


def test_market_rule_alignment_preserves_missing_provider_rule_slots() -> None:
    details = _aapl_details(market_rule_ids=(26, None))

    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    assert result.market_rule_ids == (26, None)
    assert result.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE


def test_market_rule_and_exchange_lists_must_remain_positionally_aligned() -> None:
    with pytest.raises(IBKRContractMappingError, match="positional alignment"):
        IBKRContractDetailsRecord(
            contract=_aapl_details().contract,
            valid_exchanges=("SMART", "NASDAQ"),
            market_rule_ids=(26,),
        )


def test_lot05_2_rejects_non_smart_routing() -> None:
    with pytest.raises(IBKRContractMappingError, match="SMART"):
        map_ibkr_stock_contract(
            _aapl_details(exchange="NASDAQ"),
            instrument_id=InstrumentId.new(),
        )


def test_lot05_2_rejects_non_usd_stock_currency() -> None:
    with pytest.raises(IBKRContractMappingError, match="USD"):
        map_ibkr_stock_contract(
            _aapl_details(currency="EUR"),
            instrument_id=InstrumentId.new(),
        )


def test_contract_record_normalizes_provider_labels_without_changing_symbol() -> None:
    record = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol=" aapl ",
        security_type=IBKRSecurityType.STOCK,
        exchange=" smart ",
        primary_exchange=" nasdaq ",
        currency=" usd ",
        local_symbol=" AAPL ",
        trading_class=" NMS ",
    )

    assert record.symbol == "aapl"
    assert record.exchange == "SMART"
    assert record.primary_exchange == "NASDAQ"
    assert record.currency == "USD"
    assert record.local_symbol == "AAPL"
    assert record.trading_class == "NMS"


def _invalid_min_tick() -> IBKRContractDetailsRecord:
    return IBKRContractDetailsRecord(
        contract=_aapl_details().contract,
        min_tick=Decimal("0"),
    )


def _invalid_size_increment() -> IBKRContractDetailsRecord:
    return IBKRContractDetailsRecord(
        contract=_aapl_details().contract,
        size_increment=Decimal("0"),
    )


def _invalid_suggested_size_increment() -> IBKRContractDetailsRecord:
    return IBKRContractDetailsRecord(
        contract=_aapl_details().contract,
        suggested_size_increment=Decimal("-1"),
    )


def _invalid_min_size() -> IBKRContractDetailsRecord:
    return IBKRContractDetailsRecord(
        contract=_aapl_details().contract,
        min_size=Decimal("-1"),
    )


@pytest.mark.parametrize(
    "factory",
    [
        _invalid_min_tick,
        _invalid_size_increment,
        _invalid_suggested_size_increment,
        _invalid_min_size,
    ],
)
def test_contract_details_reject_invalid_numeric_constraints(
    factory: Callable[[], IBKRContractDetailsRecord],
) -> None:
    with pytest.raises(IBKRContractMappingError):
        factory()
