"""Probe a local IB Gateway PAPER connection without placing an order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRPaperRuntimeProfile,
    build_ibkr_paper_connection_runtime,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Connect to a local IB Gateway PAPER session and capture sanitized "
            "LOT-06.1 startup evidence. This probe never submits an order."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = IBKRPaperRuntimeProfile.from_environment()
    runtime = build_ibkr_paper_connection_runtime(profile)

    try:
        report = runtime.start()
        evidence = runtime.connection_evidence

        payload = {
            "lot": "LOT-06.1",
            "release": "0.8.0b2",
            "provider": "ibkr",
            "environment": "PAPER",
            "account": profile.masked_account_id,
            "host": profile.host,
            "port": profile.port,
            "client_id": profile.client_id.value,
            "startup_report": report.to_dict(),
            "connection": (
                None
                if evidence is None
                else {
                    "transport": evidence.transport_name,
                    "transport_version": evidence.transport_version,
                    "socket_connected": evidence.socket_connected,
                    "protocol_ready": evidence.protocol_ready,
                    "account_verified": evidence.account_verified,
                    "server_version": evidence.server_version,
                }
            ),
            "economic_order_submitted": False,
            "paper_certification_claimed": False,
            "live_available": False,
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if not report.ready_for_startup:
            print("IBKR PAPER connection probe: NOT READY")
            print(f"output: {args.output}")
            return 2

        print("IBKR PAPER connection probe: PASS")
        print(f"account: {profile.masked_account_id}")
        print(f"endpoint: {profile.host}:{profile.port}")
        print("economic order submitted: false")
        print("PAPER certification claimed: false")
        print(f"output: {args.output}")
        return 0
    finally:
        runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())
