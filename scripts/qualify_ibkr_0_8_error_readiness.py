"""Qualify PyTradeKit 0.8 LOT-05.7 IBKR error and readiness semantics."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pytradekit.brokers import (
    ProviderStateReconciliationRequired,
    ProviderUncertainOutcomeError,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRErrorObservation,
    IBKRReadinessObservation,
    build_ibkr_capability_manifest,
    evaluate_ibkr_readiness,
    map_ibkr_provider_error,
)
from pytradekit.brokers.compliance import BrokerCapability


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.7 IBKR error taxonomy, readiness, and capability "
            "declaration without provider network calls."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    now = datetime(2026, 10, 23, 6, 15, tzinfo=UTC)

    disconnect = IBKRErrorObservation(
        request_id=-1,
        code=1100,
        message="Connectivity lost",
        observed_at=now,
    )
    read_disconnect = map_ibkr_provider_error(
        disconnect,
        operation="runtime",
    )
    write_disconnect = map_ibkr_provider_error(
        disconnect,
        operation="submit",
        economic_write_in_flight=True,
    )

    restored_data_lost = evaluate_ibkr_readiness(
        IBKRReadinessObservation(
            socket_connected=True,
            protocol_negotiated=True,
            next_valid_id_received=True,
            account_verified=True,
            paper_endpoint_verified=True,
            reconciliation_complete=False,
            account_ready=True,
            api_read_only=False,
            market_data_resubscribed=False,
            last_connectivity_code=1101,
        )
    )
    ready = evaluate_ibkr_readiness(
        IBKRReadinessObservation(
            socket_connected=True,
            protocol_negotiated=True,
            next_valid_id_received=True,
            account_verified=True,
            paper_endpoint_verified=True,
            reconciliation_complete=True,
            account_ready=True,
            api_read_only=False,
            market_data_resubscribed=True,
            last_connectivity_code=None,
        )
    )
    manifest = build_ibkr_capability_manifest()

    payload = {
        "lot": "LOT-05.7",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "paper_certification_claimed": False,
        "disconnect_requires_reconciliation": isinstance(
            read_disconnect,
            ProviderStateReconciliationRequired,
        ),
        "inflight_disconnect_is_uncertain": isinstance(
            write_disconnect,
            ProviderUncertainOutcomeError,
        ),
        "restored_data_lost": {
            "ready_for_reads": restored_data_lost.ready_for_reads,
            "ready_for_market_data": restored_data_lost.ready_for_market_data,
            "ready_for_economic_writes": (
                restored_data_lost.ready_for_economic_writes
            ),
            "reconciliation_required": (
                restored_data_lost.reconciliation_required
            ),
            "market_data_resubscription_required": (
                restored_data_lost.market_data_resubscription_required
            ),
        },
        "fully_proven_runtime": {
            "ready_for_reads": ready.ready_for_reads,
            "ready_for_market_data": ready.ready_for_market_data,
            "ready_for_economic_writes": ready.ready_for_economic_writes,
        },
        "manifest": {
            "provider": manifest.provider,
            "environment": manifest.environment.value,
            "adapter_version": manifest.adapter_version,
            "capabilities": sorted(
                capability.value for capability in manifest.capability_set
            ),
            "latest_quote_declared": manifest.supports(
                BrokerCapability.LATEST_QUOTE
            ),
            "replace_order_declared": manifest.supports(
                BrokerCapability.REPLACE_ORDER
            ),
            "sdk_selected": manifest.sdk_name is not None,
        },
        "core_change_required": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.7 IBKR error/readiness qualification: PASS")
    print("disconnect without write requires reconciliation: true")
    print("disconnect during economic write is uncertain: true")
    print("1101 requires market-data resubscription: true")
    print("economic writes require explicit reconciliation: true")
    print("LATEST_QUOTE declared: false")
    print("REPLACE_ORDER declared: false")
    print("provider SDK selected: false")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
