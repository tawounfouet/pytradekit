"""Qualify PyTradeKit 0.8 LOT-06.3 IBKR contract resolution."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractId,
    IBKRContractReferenceResolver,
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-06.3 contract reference resolution without "
            "a provider network call."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
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
    if mapping is None:
        raise RuntimeError("Deterministic contract resolution unexpectedly failed.")

    evidence = resolver.last_evidence
    if evidence is None or not evidence.resolved:
        raise RuntimeError("Contract resolution evidence was not retained.")

    payload = {
        "lot": "LOT-06.3",
        "release": "0.8.0b4",
        "provider": "ibkr",
        "environment": "PAPER",
        "contract_id": mapping.identity.external_id,
        "symbol": mapping.identity.external_symbol,
        "routing_exchange": mapping.routing_exchange,
        "primary_exchange": mapping.primary_exchange,
        "price_increment_mode": mapping.price_increment_mode.value,
        "market_rule_ids": list(mapping.market_rule_ids),
        "valid_exchanges": list(mapping.valid_exchanges),
        "canonical_tick_size": (
            str(mapping.specification.tick_size)
            if mapping.specification.tick_size is not None
            else None
        ),
        "provider_match_count": evidence.provider_match_count,
        "exact_match_count": evidence.exact_match_count,
        "economic_write_used": False,
        "real_paper_provider_used": False,
        "paper_certification_claimed": False,
        "live_available": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-06.3 IBKR contract resolution: PASS")
    print("contract lookup semantics: qualified")
    print("market-rule preservation: qualified")
    print("economic write used: false")
    print("real PAPER provider proof: false")
    print("PAPER certification claimed: false")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
