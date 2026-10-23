"""Unit tests for IBKR LOT-06.6 dynamic market rules."""

from decimal import Decimal

import pytest

from pytradekit.brokers import ProviderProtocolError
from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRMarketRuleResolver,
    IBKRPriceIncrement,
    IBKRSecurityType,
    ibkr_routing_market_rule_id,
    map_ibkr_stock_contract,
    normalize_ibkr_market_rule,
)
from pytradekit.shared import InstrumentId


class _RawIncrement:
    def __init__(self, low_edge: float, increment: float) -> None:
        self.lowEdge = low_edge
        self.increment = increment


class _Client:
    def __init__(self) -> None:
        self.calls = 0
        self.payload: object = [
            _RawIncrement(0.0, 0.01),
            _RawIncrement(100.0, 0.05),
        ]

    def reqMarketRule(self, marketRuleId: int) -> object:
        assert marketRuleId == 26
        self.calls += 1
        return self.payload


def _mapping(
    *,
    valid_exchanges: tuple[str, ...] = ("SMART",),
    market_rule_ids: tuple[int | None, ...] = (26,),
):
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
        trading_class="NMS",
    )
    details = IBKRContractDetailsRecord(
        contract=contract,
        min_tick=Decimal("0.01"),
        min_size=Decimal("1"),
        size_increment=Decimal("1"),
        valid_exchanges=valid_exchanges,
        market_rule_ids=market_rule_ids,
    )
    return map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )


def test_market_rule_normalization_preserves_decimal_schedule() -> None:
    rule = normalize_ibkr_market_rule(
        market_rule_id=26,
        raw_increments=[
            _RawIncrement(0.0, 0.01),
            _RawIncrement(100.0, 0.05),
        ],
    )

    assert rule.market_rule_id == 26
    assert rule.increments == (
        IBKRPriceIncrement(
            low_edge=Decimal("0.0"),
            increment=Decimal("0.01"),
        ),
        IBKRPriceIncrement(
            low_edge=Decimal("100.0"),
            increment=Decimal("0.05"),
        ),
    )


def test_dynamic_rule_selects_increment_by_low_edge() -> None:
    client = _Client()
    resolver = IBKRMarketRuleResolver(client)
    mapping = _mapping()

    lower = resolver.validate_limit_price(
        instrument=mapping,
        price=Decimal("99.99"),
    )
    upper = resolver.validate_limit_price(
        instrument=mapping,
        price=Decimal("100.10"),
    )

    assert lower.valid
    assert lower.increment == Decimal("0.01")
    assert upper.valid
    assert upper.low_edge == Decimal("100.0")
    assert upper.increment == Decimal("0.05")
    assert client.calls == 1
    assert not lower.cache_hit
    assert upper.cache_hit


def test_dynamic_rule_rejects_price_outside_active_increment_grid() -> None:
    resolver = IBKRMarketRuleResolver(_Client())

    evidence = resolver.validate_limit_price(
        instrument=_mapping(),
        price=Decimal("100.12"),
    )

    assert not evidence.valid
    assert evidence.increment == Decimal("0.05")


def test_routing_exchange_selects_positionally_aligned_market_rule() -> None:
    mapping = _mapping(
        valid_exchanges=("NASDAQ", "SMART"),
        market_rule_ids=(25, 26),
    )

    assert ibkr_routing_market_rule_id(mapping) == 26


def test_missing_routing_market_rule_fails_closed() -> None:
    mapping = _mapping(
        valid_exchanges=("NASDAQ", "SMART"),
        market_rule_ids=(25, None),
    )

    with pytest.raises(ProviderProtocolError, match="no usable market rule"):
        ibkr_routing_market_rule_id(mapping)


def test_unordered_provider_schedule_fails_closed() -> None:
    with pytest.raises(
        ProviderProtocolError,
        match="invalid increment schedule",
    ):
        normalize_ibkr_market_rule(
            market_rule_id=26,
            raw_increments=[
                _RawIncrement(100.0, 0.05),
                _RawIncrement(0.0, 0.01),
            ],
        )


def test_empty_provider_schedule_fails_closed() -> None:
    with pytest.raises(ProviderProtocolError, match="no price increments"):
        normalize_ibkr_market_rule(
            market_rule_id=26,
            raw_increments=[],
        )
