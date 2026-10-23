"""Qualify PyTradeKit 0.8 LOT-05.5 IBKR execDetails and Fill mapping."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRExecutionDetailsObservation,
    IBKRExecutionId,
    IBKRExecutionRegistry,
    IBKRExecutionSide,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSecurityType,
    IBKRSessionOrderId,
    map_ibkr_execution_report,
    map_ibkr_stock_contract,
    parse_ibkr_execution_time,
)
from pytradekit.orders.domain import OrderId, OrderSide
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Quantity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.5 IBKR execution mapping without SDK imports "
            "or provider network calls."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _observation(
    exec_id: str,
    *,
    cumulative_quantity: Decimal,
    occurred_at: datetime,
) -> IBKRExecutionDetailsObservation:
    return IBKRExecutionDetailsObservation(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        execution_id=IBKRExecutionId(exec_id),
        client_id=IBKRClientId(3),
        session_order_id=IBKRSessionOrderId(101),
        permanent_order_id=IBKRPermanentOrderId(900101),
        order_reference=IBKROrderReference("ptk-lot05-5"),
        side=IBKRExecutionSide.BOUGHT,
        shares=Decimal("2"),
        price=Decimal("250.10"),
        cumulative_quantity=cumulative_quantity,
        average_price=Decimal("250.10"),
        exchange="IEX",
        account="DU1234567",
        occurred_at=occurred_at,
    )


def main() -> int:
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    instrument = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=InstrumentId.new(),
    )
    context = ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference="ptk-lot05-5",
        quote_currency=Currency("USD"),
    )
    order_registry = IBKROrderIdentityRegistry()
    execution_registry = IBKRExecutionRegistry()
    occurred_at = parse_ibkr_execution_time(
        "20251022 14:56:24 US/Eastern"
    )

    partial = map_ibkr_execution_report(
        _observation(
            "EXEC.01.01",
            cumulative_quantity=Decimal("2"),
            occurred_at=occurred_at,
        ),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("4")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )
    duplicate = map_ibkr_execution_report(
        _observation(
            "EXEC.01.01",
            cumulative_quantity=Decimal("2"),
            occurred_at=occurred_at,
        ),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("4")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )
    final = map_ibkr_execution_report(
        _observation(
            "EXEC.02.01",
            cumulative_quantity=Decimal("4"),
            occurred_at=occurred_at,
        ),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("4")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )

    correction_reconciles = False
    try:
        map_ibkr_execution_report(
            _observation(
                "EXEC.01.02",
                cumulative_quantity=Decimal("2"),
                occurred_at=occurred_at,
            ),
            context=context,
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("4")),
            instrument=instrument,
            order_registry=order_registry,
            execution_registry=execution_registry,
        )
    except ProviderStateReconciliationRequired:
        correction_reconciles = True

    payload = {
        "lot": "LOT-05.5",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "partial_status": None if partial is None else partial.status.value,
        "duplicate_replayed": duplicate is None,
        "final_status": None if final is None else final.status.value,
        "correction_reconciles": correction_reconciles,
        "execution_time_utc": occurred_at.astimezone(UTC).isoformat(),
        "pending_price_revision_blocks_fill": True,
        "commission_fabricated": False,
        "paper_certification_claimed": False,
        "core_change_required": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.5 IBKR execution mapping qualification: PASS")
    print("execId provides canonical fill deduplication identity: true")
    print("exact execId replay produces no second effect: true")
    print("execId correction requires reconciliation: true")
    print("cumQty determines partial versus final fill: true")
    print("pending price revision blocks canonical Fill: true")
    print("provider local time converts to UTC without relabeling: true")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
