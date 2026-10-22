"""Evaluate PyTradeKit LOT-05 Alpaca PAPER startup readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pytradekit.brokers.adapters.alpaca import build_alpaca_paper_runtime
from pytradekit.runtime import EnvironmentSecrets, RuntimeProfile
from pytradekit.runtime.errors import RuntimeConfigurationError, SecretResolutionError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the PyTradeKit 0.5 Alpaca PAPER runtime bootstrap. "
            "This command is read-only and has no LIVE mode."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional sanitized JSON report path. Defaults to stdout.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        profile = RuntimeProfile.alpaca_paper_from_environment()
        composition = build_alpaca_paper_runtime(
            profile,
            EnvironmentSecrets(),
        )
        report = composition.readiness.run()
    except (RuntimeConfigurationError, SecretResolutionError, ValueError) as exc:
        print(f"Runtime bootstrap configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - real infrastructure/provider boundary
        print(
            "Alpaca PAPER runtime bootstrap failed "
            f"({type(exc).__name__}). No trading command is executed by this readiness check.",
            file=sys.stderr,
        )
        return 1

    payload = {
        "profile": {
            "name": profile.name,
            "provider": profile.provider,
            "environment": profile.environment.value,
            "account": profile.masked_account_id,
            "market_data_feed": profile.market_data_feed,
        },
        "manifest": composition.manifest.to_dict(),
        "readiness": report.to_dict(),
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True)

    output: Path | None = args.output
    if output is None:
        print(encoded)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
        print(f"Wrote sanitized Alpaca PAPER startup readiness report to {output}")

    return 0 if report.ready_for_startup else 1


if __name__ == "__main__":
    raise SystemExit(main())
