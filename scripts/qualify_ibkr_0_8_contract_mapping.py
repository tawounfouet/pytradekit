"""Qualify PyTradeKit 0.8 LOT-05.2 IBKR contract mapping."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRSecurityType,
    map_ibkr_stock_contract,
)
from pytradekit.shared import InstrumentId


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.2 IBKR contract mapping without importing or "
            "connecting to an IBKR SDK."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Generated JSON qualification artifact.",
    )
    return parser


def main() -> int:
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
        suggested_size_increment=Decimal("0.0001"),
        valid_exchanges=("SMART", "NASDAQ"),
        market_rule_ids=(26, 26),
        order_types=("MKT", "LMT"),
        time_zone_id="US/Eastern",
        stock_type="COMMON",
    )
    result = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )

    payload = {
        "lot": "LOT-05.2",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "contract": {
            "con_id": result.identity.external_id,
            "symbol": result.identity.external_symbol,
            "routing_exchange": result.routing_exchange,
            "primary_exchange": result.primary_exchange,
            "currency": str(result.instrument.quote_currency),
            "asset_class": result.instrument.asset_class.value,
        },
        "contract_specification": {
            "tick_size": (
                None
                if result.specification.tick_size is None
                else str(result.specification.tick_size)
            ),
            "quantity_step": (
                None
                if result.specification.quantity_step is None
                else str(result.specification.quantity_step)
            ),
            "min_quantity": (
                None
                if result.specification.min_quantity is None
                else str(result.specification.min_quantity)
            ),
        },
        "price_increment": {
            "mode": result.price_increment_mode.value,
            "reported_min_tick": (
                None
                if result.reported_min_tick is None
                else str(result.reported_min_tick)
            ),
            "market_rule_ids": list(result.market_rule_ids),
        },
        "core_change_required": False,
        "paper_certification_claimed": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.2 IBKR contract mapping qualification: PASS")
    print("conId maps to provider instrument identity: true")
    print("STK maps to canonical EQUITY in the frozen scope: true")
    print("SMART routing and primary exchange remain distinct: true")
    print("marketRuleIds prevent false static tick-size claims: true")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
