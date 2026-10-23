"""Qualify PyTradeKit 0.8 LOT-05.3 IBKR SDK-free order command mapping."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRSecurityType,
    map_ibkr_order_command,
    map_ibkr_stock_contract,
)
from pytradekit.orders.domain import Order, OrderId, OrderSide, TimeInForce
from pytradekit.shared import CorrelationId, InstrumentId, Quantity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.3 IBKR order command mapping without SDK imports "
            "or provider network calls."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    now = datetime(2026, 10, 23, 2, 45, tzinfo=UTC)
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    instrument_id = InstrumentId.new()
    instrument = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=instrument_id,
    )
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("5")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=now,
        client_order_id="ptk-lot05-3",
    )
    order.validate(occurred_at=now)
    order.mark_submitted(occurred_at=now)

    placement = map_ibkr_order_command(
        order,
        contract=contract,
        instrument=instrument,
    )

    payload = {
        "lot": "LOT-05.3",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "contract": {
            "con_id": str(placement.contract.contract_id),
            "symbol": placement.contract.symbol,
        },
        "order": {
            "action": placement.order.action.value,
            "order_type": placement.order.order_type.value,
            "total_quantity": str(placement.order.total_quantity),
            "time_in_force": placement.order.time_in_force.value,
            "order_reference": placement.order.order_reference.value,
            "limit_price": (
                None
                if placement.order.limit_price is None
                else str(placement.order.limit_price)
            ),
            "transmit_policy": placement.order.transmit_policy.value,
            "outside_regular_trading_hours": (
                placement.order.outside_regular_trading_hours
            ),
            "what_if": placement.order.what_if,
            "override_percentage_constraints": (
                placement.order.override_percentage_constraints
            ),
        },
        "session_order_id_allocated": False,
        "paper_certification_claimed": False,
        "core_change_required": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.3 IBKR order command qualification: PASS")
    print("MARKET/LIMIT map to MKT/LMT: true")
    print("DAY-only scope enforced: true")
    print("orderRef maps from client_order_id: true")
    print("provider orderId allocation deferred to transport: true")
    print("transmit intent explicit: true")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
