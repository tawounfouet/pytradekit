"""Safely probe IBKR PAPER contract resolution without economic writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractId,
    IBKRPaperRuntimeProfile,
    StaticIBKRCanonicalInstrumentIdResolver,
    build_ibkr_contract_reference_resolver,
    build_ibkr_paper_connection_runtime,
)
from pytradekit.shared import InstrumentId


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve one IBKR PAPER conId through reqContractDetails. "
            "This probe never places or cancels an order."
        )
    )
    parser.add_argument("--contract-id", type=int, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--instrument-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    contract_id = IBKRContractId(args.contract_id)
    symbol = args.symbol.strip()
    if not symbol:
        raise ValueError("--symbol must be non-empty.")
    instrument_id = InstrumentId.from_string(args.instrument_id)

    profile = IBKRPaperRuntimeProfile.from_environment()
    connection = build_ibkr_paper_connection_runtime(profile)
    try:
        startup = connection.start()
        if not startup.ready_for_startup:
            raise RuntimeError(
                "IBKR PAPER startup readiness did not pass."
            )

        resolver = build_ibkr_contract_reference_resolver(
            connection=connection,
            instrument_ids=StaticIBKRCanonicalInstrumentIdResolver(
                {(contract_id.value, symbol): instrument_id}
            ),
        )
        mapping = resolver.resolve(
            contract_id=contract_id,
            symbol=symbol,
        )
        if mapping is None:
            raise RuntimeError(
                "IBKR PAPER contract lookup returned no exact mapping."
            )

        evidence = resolver.last_evidence
        if evidence is None:
            raise RuntimeError(
                "IBKR PAPER contract evidence was not retained."
            )

        payload = {
            "lot": "LOT-06.3",
            "provider": "ibkr",
            "environment": "PAPER",
            "account": profile.masked_account_id,
            "contract_id": mapping.identity.external_id,
            "symbol": mapping.identity.external_symbol,
            "routing_exchange": mapping.routing_exchange,
            "primary_exchange": mapping.primary_exchange,
            "local_symbol": mapping.local_symbol,
            "trading_class": mapping.trading_class,
            "valid_exchanges": list(mapping.valid_exchanges),
            "market_rule_ids": list(mapping.market_rule_ids),
            "price_increment_mode": mapping.price_increment_mode.value,
            "reported_min_tick": (
                str(mapping.reported_min_tick)
                if mapping.reported_min_tick is not None
                else None
            ),
            "quantity_step": (
                str(mapping.specification.quantity_step)
                if mapping.specification.quantity_step is not None
                else None
            ),
            "min_quantity": (
                str(mapping.specification.min_quantity)
                if mapping.specification.min_quantity is not None
                else None
            ),
            "provider_match_count": evidence.provider_match_count,
            "exact_match_count": evidence.exact_match_count,
            "economic_write_used": False,
            "paper_certification_claimed": False,
            "live_available": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    finally:
        connection.stop()

    print("IBKR PAPER contract resolution probe: PASS")
    print("economic write used: false")
    print("PAPER certification claimed: false")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
