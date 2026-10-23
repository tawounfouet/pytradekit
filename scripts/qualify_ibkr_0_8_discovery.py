"""Qualify the PyTradeKit 0.8.0a4 IBKR discovery contract freeze."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRClientSurface,
    build_ibkr_contract_freeze,
    validate_ibkr_paper_port,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the dependency-free IBKR discovery and contract freeze. "
            "This command does not connect to IBKR and has no LIVE mode."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Generated JSON contract-freeze artifact.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        freeze = build_ibkr_contract_freeze()
        validate_ibkr_paper_port(
            surface=IBKRClientSurface.IB_GATEWAY,
            port=freeze.paper_port,
        )
        if freeze.broker_neutral_core_change_required:
            raise RuntimeError(
                "LOT-04 discovered an IBKR-specific broker-neutral core change."
            )
    except Exception as exc:
        print(
            f"PyTradeKit 0.8 IBKR discovery contract freeze: FAIL ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1

    payload = freeze.to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 IBKR discovery contract freeze: PASS")
    print(f"provider: {freeze.provider}")
    print(f"environment: {freeze.environment.value}")
    print(f"runtime surface: {freeze.runtime_surface.value}")
    print(f"paper port: {freeze.paper_port}")
    print(f"target capabilities: {len(freeze.target_capabilities)}")
    print(f"deferred capabilities: {len(freeze.deferred_capabilities)}")
    print(f"open PAPER questions: {len(freeze.unresolved_paper_questions)}")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
