"""Unit tests for IBKR LOT-06.3 contract reference resolution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from pytradekit.brokers import ProviderProtocolError
from pytradekit.brokers.adapters.ibkr import (
    IBAsyncContractRequestFactory,
    IBKRCanonicalInstrumentIdResolver,
    IBKRContractId,
    IBKRContractReferenceResolver,
    IBKRContractResolutionError,
    IBKRPriceIncrementMode,
    StaticIBKRCanonicalInstrumentIdResolver,
    normalize_ibkr_contract_details,
)
from pytradekit.shared import InstrumentId


@dataclass
class _Contract:
    conId: int = 265598
    symbol: str = "AAPL"
    secType: str = "STK"
    exchange: str = "SMART"
    primaryExchange: str = "NASDAQ"
    currency: str = "USD"
    localSymbol: str = "AAPL"
    tradingClass: str = "NMS"


@dataclass
class _Details:
    contract: object | None
    minTick: object = 0.01
    minSize: object = 0.0001
    sizeIncrement: object = 0.0001
    suggestedSizeIncrement: object = 0.0001
    validExchanges: str = "SMART,NASDAQ"
    marketRuleIds: str = "26,26"
    orderTypes: str = "MKT,LMT"
    timeZoneId: str = "US/Eastern"
    stockType: str = "COMMON"


@dataclass
class _Request:
    con_id: int


class _RequestFactory:
    def __init__(self) -> None:
        self.requests: list[int] = []

    def build(self, *, contract_id: IBKRContractId) -> object:
        self.requests.append(contract_id.value)
        return _Request(contract_id.value)


class _Client:
    def __init__(self, matches: list[object]) -> None:
        self.matches = matches
        self.calls = 0

    def reqContractDetails(self, contract: object) -> list[object]:
        self.calls += 1
        return list(self.matches)


def _instrument_ids(
    instrument_id: InstrumentId | None = None,
) -> StaticIBKRCanonicalInstrumentIdResolver:
    return StaticIBKRCanonicalInstrumentIdResolver(
        {
            (265598, "AAPL"): instrument_id or InstrumentId.new(),
        }
    )


def _resolver(
    matches: list[object],
    *,
    instrument_ids: IBKRCanonicalInstrumentIdResolver | None = None,
) -> tuple[
    IBKRContractReferenceResolver,
    _Client,
    _RequestFactory,
]:
    client = _Client(matches)
    factory = _RequestFactory()
    resolver = IBKRContractReferenceResolver(
        client=client,
        instrument_ids=instrument_ids or _instrument_ids(),
        request_factory=factory,
    )
    return resolver, client, factory


def test_exact_contract_details_resolve_into_lot05_mapping() -> None:
    instrument_id = InstrumentId.new()
    resolver, client, factory = _resolver(
        [_Details(contract=_Contract())],
        instrument_ids=_instrument_ids(instrument_id),
    )

    result = resolver.resolve(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )

    assert result is not None
    assert result.instrument.id == instrument_id
    assert result.identity.external_id == "265598"
    assert result.identity.external_symbol == "AAPL"
    assert result.routing_exchange == "SMART"
    assert result.primary_exchange == "NASDAQ"
    assert result.specification.tick_size is None
    assert result.specification.min_quantity == Decimal("0.0001")
    assert result.specification.quantity_step == Decimal("0.0001")
    assert result.market_rule_ids == (26, 26)
    assert result.valid_exchanges == ("SMART", "NASDAQ")
    assert result.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE
    assert client.calls == 1
    assert factory.requests == [265598]

    evidence = resolver.last_evidence
    assert evidence is not None
    assert evidence.resolved
    assert evidence.provider_match_count == 1
    assert evidence.exact_match_count == 1
    assert evidence.canonical_instrument_id == instrument_id


def test_resolver_caches_exact_mapping_without_second_provider_call() -> None:
    resolver, client, _factory = _resolver(
        [_Details(contract=_Contract())]
    )

    first = resolver.resolve(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )
    second = resolver.resolve(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )

    assert first == second
    assert client.calls == 1


def test_missing_canonical_instrument_id_avoids_provider_lookup() -> None:
    class _Missing:
        def resolve_instrument_id(
            self,
            *,
            contract_id: IBKRContractId,
            symbol: str,
        ) -> InstrumentId | None:
            return None

    resolver, client, factory = _resolver(
        [_Details(contract=_Contract())],
        instrument_ids=_Missing(),
    )

    result = resolver.resolve(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )

    assert result is None
    assert client.calls == 0
    assert factory.requests == []
    assert resolver.last_evidence is not None
    assert not resolver.last_evidence.resolved


def test_empty_provider_result_remains_unresolved() -> None:
    resolver, client, _factory = _resolver([])

    result = resolver.resolve(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )

    assert result is None
    assert client.calls == 1
    assert resolver.last_evidence is not None
    assert resolver.last_evidence.provider_match_count == 0


def test_multiple_exact_matches_fail_closed() -> None:
    resolver, _client, _factory = _resolver(
        [
            _Details(contract=_Contract()),
            _Details(contract=_Contract()),
        ]
    )

    with pytest.raises(ProviderProtocolError, match="exactly one"):
        resolver.resolve(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
        )


def test_provider_con_id_mismatch_fails_closed() -> None:
    resolver, _client, _factory = _resolver(
        [
            _Details(
                contract=_Contract(conId=999999),
            )
        ]
    )

    with pytest.raises(ProviderProtocolError, match="exactly one"):
        resolver.resolve(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
        )


def test_provider_symbol_mismatch_fails_closed() -> None:
    resolver, _client, _factory = _resolver(
        [
            _Details(
                contract=_Contract(symbol="MSFT"),
            )
        ]
    )

    with pytest.raises(ProviderProtocolError, match="exactly one"):
        resolver.resolve(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
        )


def test_zero_provider_defaults_do_not_fabricate_constraints() -> None:
    details = normalize_ibkr_contract_details(
        _Details(
            contract=_Contract(),
            minTick=0,
            minSize=0,
            sizeIncrement=0,
            suggestedSizeIncrement=0,
            marketRuleIds="",
        )
    )

    assert details.min_tick is None
    assert details.min_size is None
    assert details.size_increment is None
    assert details.suggested_size_increment is None


def test_market_rule_alignment_preserves_empty_provider_slots() -> None:
    details = normalize_ibkr_contract_details(
        _Details(
            contract=_Contract(),
            validExchanges="SMART,NASDAQ,NYSE",
            marketRuleIds="26,,28",
        )
    )

    assert details.valid_exchanges == ("SMART", "NASDAQ", "NYSE")
    assert details.market_rule_ids == (26, None, 28)


def test_invalid_market_rule_id_is_rejected() -> None:
    with pytest.raises(
        IBKRContractResolutionError,
        match="non-integer",
    ):
        normalize_ibkr_contract_details(
            _Details(
                contract=_Contract(),
                marketRuleIds="26,bad",
            )
        )


def test_non_stock_contract_is_rejected() -> None:
    with pytest.raises(
        IBKRContractResolutionError,
        match="security type",
    ):
        normalize_ibkr_contract_details(
            _Details(
                contract=_Contract(secType="OPT"),
            )
        )


def test_request_factory_uses_con_id_and_smart_only() -> None:
    captured: dict[str, object] = {}

    def constructor(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    factory = IBAsyncContractRequestFactory(
        constructor=constructor,
    )

    request = factory.build(
        contract_id=IBKRContractId(265598),
    )

    assert request is not None
    assert captured == {
        "conId": 265598,
        "exchange": "SMART",
    }


def test_static_instrument_resolver_requires_exact_symbol() -> None:
    instrument_id = InstrumentId.new()
    resolver = _instrument_ids(instrument_id)

    assert (
        resolver.resolve_instrument_id(
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
        )
        == instrument_id
    )
    assert (
        resolver.resolve_instrument_id(
            contract_id=IBKRContractId(265598),
            symbol="MSFT",
        )
        is None
    )
