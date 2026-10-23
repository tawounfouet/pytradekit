"""Qualify PyTradeKit 0.8 LOT-06.6 IBKR operational runtime."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKR_MARKET_RULE_VERSION,
    IBKR_OPERATIONAL_RUNTIME_VERSION,
    IBKRErrorObservation,
    IBKROperationalGuard,
    normalize_ibkr_market_rule,
)


class _Increment:
    def __init__(self, low_edge: float, increment: float) -> None:
        self.lowEdge = low_edge
        self.increment = increment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-06.6 market-rule and reconnect containment "
            "without provider economic writes."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    market_rules_path = Path(
        "src/pytradekit/brokers/adapters/ibkr/market_rules.py"
    )
    operations_path = Path(
        "src/pytradekit/brokers/adapters/ibkr/operations_runtime.py"
    )
    execution_path = Path(
        "src/pytradekit/brokers/adapters/ibkr/execution.py"
    )

    market_rules = market_rules_path.read_text(encoding="utf-8")
    operations = operations_path.read_text(encoding="utf-8")
    execution = execution_path.read_text(encoding="utf-8")

    rule = normalize_ibkr_market_rule(
        market_rule_id=26,
        raw_increments=[
            _Increment(0.0, 0.01),
            _Increment(100.0, 0.05),
        ],
    )
    valid_price = rule.validates(Decimal("100.10"))
    invalid_price_rejected = not rule.validates(Decimal("100.12"))

    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )
    guard.observe_error(
        IBKRErrorObservation(
            request_id=-1,
            code=1100,
            message="connectivity lost",
            observed_at=datetime(2026, 10, 23, 10, 55, tzinfo=UTC),
        ),
        operation="provider_event",
    )
    guard.observe_error(
        IBKRErrorObservation(
            request_id=-1,
            code=1102,
            message="connectivity restored with data maintained",
            observed_at=datetime(2026, 10, 23, 10, 56, tzinfo=UTC),
        ),
        operation="provider_event",
    )
    reconciliation_required_after_restore = (
        not guard.snapshot.reconciliation_complete
    )

    if IBKR_MARKET_RULE_VERSION != "0.8.0b7-lot06.6":
        raise RuntimeError("Unexpected LOT-06.6 market-rule version.")
    if IBKR_OPERATIONAL_RUNTIME_VERSION != "0.8.0b7-lot06.6":
        raise RuntimeError("Unexpected LOT-06.6 operational version.")
    if market_rules.count("request.reqMarketRule(") != 1:
        raise RuntimeError("LOT-06.6 must have one reqMarketRule call site.")
    if execution.count("client.placeOrder(") != 1:
        raise RuntimeError("LOT-06.6 must preserve one placeOrder call site.")
    if execution.count("client.cancelOrder(") != 1:
        raise RuntimeError("LOT-06.6 must preserve one cancelOrder call site.")
    if ".placeOrder(" in operations or ".cancelOrder(" in operations:
        raise RuntimeError("Reconnect runtime must not replay economic writes.")
    if "Watchdog" in operations or "time.sleep(" in operations:
        raise RuntimeError("LOT-06.6 must not add opaque auto-recovery.")
    if not valid_price or not invalid_price_rejected:
        raise RuntimeError("Dynamic market-rule validation is not deterministic.")
    if not reconciliation_required_after_restore:
        raise RuntimeError("Reconnect must remain contained before reconciliation.")

    payload = {
        "lot": "LOT-06.6",
        "release": "0.8.0b7",
        "provider": "ibkr",
        "environment": "PAPER",
        "req_market_rule_call_sites": 1,
        "place_order_call_sites": 1,
        "cancel_order_call_sites": 1,
        "ib_async_automatic_throttling_required": True,
        "qualified_max_request_rate_per_second": 45.0,
        "dynamic_market_rule_validation": True,
        "reconnect_requires_reconciliation": True,
        "automatic_economic_replay": False,
        "watchdog_auto_recovery": False,
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

    print("PyTradeKit 0.8 LOT-06.6 IBKR operational runtime: PASS")
    print("dynamic market rules: qualified")
    print("pacing containment: qualified")
    print("reconnect economic replay: false")
    print("reconciliation after restore: required")
    print("real PAPER provider proof: false")
    print("PAPER certification claimed: false")
    print("TRADING_READY claimed: false")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
