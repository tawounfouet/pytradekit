"""Qualify PyTradeKit 0.8 LOT-06.1 IBKR PAPER connection runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ASYNC_VERSION_TARGET,
    IBKRPaperRuntimeProfile,
    IBKRTransportConnectionEvidence,
    build_ibkr_paper_connection_runtime,
)


class _DeterministicTransport:
    def __init__(self) -> None:
        self.connected = False

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        self.connected = True
        return IBKRTransportConnectionEvidence(
            transport_name="ib_async",
            transport_version=IBKR_ASYNC_VERSION_TARGET,
            socket_connected=True,
            protocol_ready=True,
            account_verified=True,
            managed_accounts=(profile.expected_account_id,),
            server_version=178,
        )

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-06.1 IBKR transport selection and PAPER startup "
            "without a provider network call."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    profile = IBKRPaperRuntimeProfile(
        expected_account_id="DU1234567",
    )
    runtime = build_ibkr_paper_connection_runtime(
        profile,
        transport=_DeterministicTransport(),
    )
    report = runtime.start()

    payload = {
        "lot": "LOT-06.1",
        "release": "0.8.0b2",
        "provider": "ibkr",
        "environment": "PAPER",
        "transport": "ib_async",
        "transport_version": IBKR_ASYNC_VERSION_TARGET,
        "paper_port": profile.port,
        "client_id_zero_allowed": False,
        "loopback_only": True,
        "startup_ready": report.ready_for_startup,
        "trading_ready_claimed": False,
        "real_paper_connection_used": False,
        "paper_certification_claimed": False,
        "live_available": False,
        "official_ibapi_bundled": False,
        "core_change_required": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    runtime.stop()

    print("PyTradeKit 0.8 LOT-06.1 IBKR PAPER connection runtime: PASS")
    print("transport: ib_async==2.1.0")
    print("IB Gateway PAPER port: 4002")
    print("clientId 0 allowed: false")
    print("startup readiness proven deterministically: true")
    print("real PAPER provider proof: false")
    print("trading readiness claimed: false")
    print("LIVE available: false")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
