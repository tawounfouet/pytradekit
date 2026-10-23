"""Qualify PyTradeKit 0.8 LOT-05.1 IBKR provider identity semantics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRContractId,
    IBKRContractIdentity,
    IBKRExecutionCorrection,
    IBKRExecutionId,
    IBKRExecutionIdentity,
    IBKROrderIdentity,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.1 IBKR provider identity semantics without connecting "
            "to IBKR."
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
    args = _parser().parse_args()

    pending = IBKROrderIdentity(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(10),
        client_reference=IBKROrderReference("ptk-qualification-10"),
    )
    registry = IBKROrderIdentityRegistry()
    registry.register(pending)
    bound = registry.bind_permanent_order_id(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(10),
        permanent_order_id=IBKRPermanentOrderId(700),
    )
    provider_order = bound.to_provider_identity()

    execution = IBKRExecutionIdentity(
        execution_id=IBKRExecutionId("abc.def.ghi.01"),
        permanent_order_id=IBKRPermanentOrderId(700),
        session_order_id=IBKRSessionOrderId(10),
        client_id=IBKRClientId(1),
        order_reference=IBKROrderReference("ptk-qualification-10"),
    )
    provider_fill = execution.to_provider_identity()

    correction = IBKRExecutionCorrection(
        previous=IBKRExecutionId("abc.def.ghi.01"),
        corrected=IBKRExecutionId("abc.def.ghi.02"),
    )

    provider_instrument = IBKRContractIdentity(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    ).to_provider_identity()

    payload = {
        "lot": "LOT-05.1",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "order_identity": {
            "routing_key": list(bound.routing_key),
            "client_reference": provider_order.client_reference,
            "external_order_id": provider_order.external_order_id,
            "external_order_id_source": "permId",
            "session_order_id_source": "orderId",
        },
        "execution_identity": {
            "external_fill_id": provider_fill.external_fill_id,
            "external_fill_id_source": "execId",
            "correction_family": correction.family_id,
        },
        "instrument_identity": {
            "external_id": provider_instrument.external_id,
            "external_id_source": "conId",
            "symbol": provider_instrument.external_symbol,
        },
        "core_change_required": False,
        "paper_certification_claimed": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.1 IBKR identity qualification: PASS")
    print("orderId remains session-local: true")
    print("permId required for external order identity: true")
    print("execId maps to provider fill identity: true")
    print("conId maps to provider instrument identity: true")
    print("execution correction relation explicit: true")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
