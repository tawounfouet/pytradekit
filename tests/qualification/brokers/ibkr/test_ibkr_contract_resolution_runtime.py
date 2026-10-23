"""Qualification tests for IBKR LOT-06.3 contract resolution."""

from dataclasses import dataclass

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractId,
    IBKRContractReferenceResolver,
    IBKRPriceIncrementMode,
    StaticIBKRCanonicalInstrumentIdResolver,
)
from pytradekit.shared import InstrumentId


@dataclass
class _Contract:
    conId: int
    symbol: str
    secType: str
    exchange: str
    primaryExchange: str
    currency: str
    localSymbol: str
    tradingClass: str


@dataclass
class _Details:
    contract: object
    minTick: object
    minSize: object
    sizeIncrement: object
    suggestedSizeIncrement: object
    validExchanges: str
    marketRuleIds: str
    orderTypes: str
    timeZoneId: str
    stockType: str


class _Client:
    def reqContractDetails(self, contract: object) -> list[object]:
        return [
            _Details(
                contract=_Contract(
                    conId=265598,
                    symbol="AAPL",
                    secType="STK",
                    exchange="SMART",
                    primaryExchange="NASDAQ",
                    currency="USD",
                    localSymbol="AAPL",
                    tradingClass="NMS",
                ),
                minTick=0.01,
                minSize=0.0001,
                sizeIncrement=0.0001,
                suggestedSizeIncrement=0.0001,
                validExchanges="SMART,NASDAQ",
                marketRuleIds="26,26",
                orderTypes="MKT,LMT",
                timeZoneId="US/Eastern",
                stockType="COMMON",
            )
        ]


class _Factory:
    def build(self, *, contract_id: IBKRContractId) -> object:
        return {"conId": contract_id.value, "exchange": "SMART"}


def test_lot06_3_qualifies_reference_mapping_without_economic_write() -> None:
    instrument_id = InstrumentId.new()
    resolver = IBKRContractReferenceResolver(
        client=_Client(),
        instrument_ids=StaticIBKRCanonicalInstrumentIdResolver(
            {(265598, "AAPL"): instrument_id}
        ),
        request_factory=_Factory(),
    )

    mapping = resolver.resolve(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )

    assert mapping is not None
    assert mapping.instrument.id == instrument_id
    assert mapping.identity.external_id == "265598"
    assert mapping.routing_exchange == "SMART"
    assert mapping.primary_exchange == "NASDAQ"
    assert mapping.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE
    assert mapping.specification.tick_size is None
    assert mapping.market_rule_ids == (26, 26)

    evidence = resolver.last_evidence
    assert evidence is not None
    assert evidence.resolved
    assert evidence.provider_match_count == 1
    assert evidence.exact_match_count == 1
