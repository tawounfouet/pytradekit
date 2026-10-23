"""Qualify PyTradeKit 0.8 LOT-06.5 IBKR economic-write execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ECONOMIC_WRITE_VERSION,
    IBKREconomicWriteAdmission,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-06.5 economic-write architecture without "
            "sending a provider order."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    source_path = Path(
        "src/pytradekit/brokers/adapters/ibkr/execution.py"
    )
    source = source_path.read_text(encoding="utf-8")

    place_order_call_sites = source.count("client.placeOrder(")
    cancel_order_call_sites = source.count("client.cancelOrder(")
    retry_markers = {
        "for_attempt": "for attempt in" in source,
        "while_true": "while True" in source,
        "retry_call": "retry(" in source,
        "tenacity": "tenacity" in source,
        "backoff": "backoff" in source,
    }

    if IBKR_ECONOMIC_WRITE_VERSION != "0.8.0b6-lot06.5":
        raise RuntimeError("Unexpected LOT-06.5 execution version.")
    if place_order_call_sites != 1:
        raise RuntimeError("LOT-06.5 must have exactly one placeOrder call site.")
    if cancel_order_call_sites != 1:
        raise RuntimeError("LOT-06.5 must have exactly one cancelOrder call site.")
    if any(retry_markers.values()):
        raise RuntimeError("LOT-06.5 must not contain automatic retry logic.")
    if "IBKRPriceIncrementMode.MARKET_RULE" not in source:
        raise RuntimeError("Dynamic market-rule guard is missing.")
    if "external_order_id=str(permanent_order_id)" not in source:
        raise RuntimeError("permId external identity mapping is missing.")

    admission = IBKREconomicWriteAdmission(
        paper_endpoint_verified=True,
        account_ready=True,
        reconciliation_complete=True,
        api_read_only=False,
        economic_write_enabled=True,
    )
    if not admission.admitted:
        raise RuntimeError("Qualified admission fixture should be admitted.")

    payload = {
        "lot": "LOT-06.5",
        "release": "0.8.0b6",
        "provider": "ibkr",
        "environment": "PAPER",
        "place_order_call_sites": place_order_call_sites,
        "cancel_order_call_sites": cancel_order_call_sites,
        "automatic_retry_present": any(retry_markers.values()),
        "explicit_write_admission": True,
        "prewrite_session_reservation": True,
        "perm_id_is_external_order_id": True,
        "session_order_id_is_external_order_id": False,
        "dynamic_market_rule_limit_write_enabled": False,
        "economic_write_implementation_present": True,
        "real_paper_provider_used": False,
        "paper_certification_claimed": False,
        "trading_ready_claimed": False,
        "live_available": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-06.5 IBKR economic write: PASS")
    print("single placeOrder call site: qualified")
    print("single cancelOrder call site: qualified")
    print("automatic retry: false")
    print("real PAPER provider proof: false")
    print("PAPER certification claimed: false")
    print("TRADING_READY claimed: false")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
