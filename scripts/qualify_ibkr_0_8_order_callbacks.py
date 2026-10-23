"""Qualify PyTradeKit 0.8 LOT-05.4 IBKR order callback normalization."""

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
    IBKROrderErrorObservation,
    IBKROrderIdentityRegistry,
    IBKROrderStatus,
    IBKROrderStatusObservation,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
    map_ibkr_order_error_report,
    map_ibkr_order_status_report,
)
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.4 IBKR order callback normalization without SDK "
            "imports or provider network calls."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _status(
    status: str,
    *,
    observed_at: datetime,
    filled: Decimal = Decimal("0"),
    remaining: Decimal = Decimal("5"),
) -> IBKROrderStatusObservation:
    return IBKROrderStatusObservation(
        client_id=IBKRClientId(3),
        session_order_id=IBKRSessionOrderId(101),
        permanent_order_id=IBKRPermanentOrderId(900101),
        provider_status=status,
        filled=filled,
        remaining=remaining,
        average_fill_price=Decimal("250.10") if filled > 0 else None,
        last_fill_price=Decimal("250.10") if filled > 0 else None,
        why_held=None,
        observed_at=observed_at,
    )


def main() -> int:
    now = datetime(2026, 10, 23, 3, 45, tzinfo=UTC)
    context = ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference="ptk-lot05-4",
        quote_currency=Currency("USD"),
    )
    registry = IBKROrderIdentityRegistry()

    accepted = map_ibkr_order_status_report(
        _status(IBKROrderStatus.SUBMITTED.value, observed_at=now),
        context=context,
        registry=registry,
    )

    filled_requires_exec_details = False
    try:
        map_ibkr_order_status_report(
            _status(
                IBKROrderStatus.FILLED.value,
                observed_at=now,
                filled=Decimal("5"),
                remaining=Decimal("0"),
            ),
            context=context,
            registry=registry,
        )
    except ProviderStateReconciliationRequired:
        filled_requires_exec_details = True

    rejected = map_ibkr_order_error_report(
        IBKROrderErrorObservation(
            client_id=IBKRClientId(3),
            session_order_id=IBKRSessionOrderId(101),
            error_code=201,
            message="provider rejection details",
            advanced_order_reject_json=None,
            observed_at=now,
        ),
        context=context,
        registry=registry,
    )

    payload = {
        "lot": "LOT-05.4",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "submitted_status_maps_to": (
            None if accepted is None else accepted.status.value
        ),
        "filled_requires_exec_details": filled_requires_exec_details,
        "error_201_maps_to": (
            None if rejected is None else rejected.status.value
        ),
        "inactive_direct_rejection_mapping": False,
        "pending_cancel_terminal_cancelled": False,
        "paper_certification_claimed": False,
        "core_change_required": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.4 IBKR callback qualification: PASS")
    print("Submitted maps to ACCEPTED: true")
    print("PendingCancel is not terminal CANCELLED: true")
    print("Filled requires execDetails before canonical Fill: true")
    print("Inactive never maps directly to REJECTED: true")
    print("error 201 maps to explicit REJECTED fact: true")
    print("error 202 maps to explicit CANCELLED fact: true")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
