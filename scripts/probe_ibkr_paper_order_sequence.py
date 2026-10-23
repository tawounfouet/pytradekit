"""Probe the synchronized IBKR PAPER order sequence without placing an order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytradekit.brokers import ProviderExecutionContext
from pytradekit.brokers.adapters.ibkr import (
    IBKRPaperRuntimeProfile,
    build_ibkr_order_session_runtime,
    build_ibkr_paper_connection_runtime,
)
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reserve one synchronized IBKR PAPER order ID after startup. "
            "The probe never calls placeOrder or cancelOrder."
        )
    )
    parser.add_argument("--order-reference", required=True)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    order_reference = args.order_reference.strip()
    if not order_reference:
        raise ValueError("--order-reference must be non-empty.")

    profile = IBKRPaperRuntimeProfile.from_environment()
    connection = build_ibkr_paper_connection_runtime(profile)
    try:
        startup = connection.start()
        if not startup.ready_for_startup:
            raise RuntimeError("IBKR PAPER startup readiness did not pass.")

        runtime = build_ibkr_order_session_runtime(connection=connection)
        reservation = runtime.reserve(
            ProviderExecutionContext(
                order_id=OrderId.new(),
                correlation_id=CorrelationId.new(),
                client_order_reference=order_reference,
                quote_currency=Currency(args.currency),
            )
        )

        payload = {
            "lot": "LOT-06.4",
            "release": "0.8.0b5",
            "provider": "ibkr",
            "environment": "PAPER",
            "account": profile.masked_account_id,
            "client_id": reservation.client_id.value,
            "session_order_id": reservation.session_order_id.value,
            "order_reference": reservation.order_reference.value,
            "protocol_ready": True,
            "next_valid_id_sequence_available": True,
            "economic_write_used": False,
            "place_order_used": False,
            "cancel_order_used": False,
            "paper_certification_claimed": False,
            "trading_ready_claimed": False,
            "live_available": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    finally:
        connection.stop()

    print("IBKR PAPER order-sequence probe: PASS")
    print("economic write used: false")
    print("placeOrder used: false")
    print("cancelOrder used: false")
    print("PAPER certification claimed: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
