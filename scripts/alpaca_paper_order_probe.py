"""Run the PyTradeKit controlled Alpaca PAPER order probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pytradekit.brokers.adapters.alpaca import (
    AlpacaPaperOrderProbeConfig,
    build_alpaca_paper_order_probe,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Controlled Alpaca PAPER order probe. This command creates simulated PAPER "
            "orders and has no LIVE mode. Credentials and the explicit acknowledgement "
            "are read from environment variables."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional sanitized JSON output path. Defaults to stdout.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        config = AlpacaPaperOrderProbeConfig.from_environment()
        report = build_alpaca_paper_order_probe(config).run()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - real provider boundary
        print(
            "Alpaca controlled PAPER order probe failed before a report could be produced "
            f"({type(exc).__name__}). Inspect the PAPER account before retrying.",
            file=sys.stderr,
        )
        return 1

    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    output: Path | None = args.output
    if output is None:
        print(payload)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote sanitized Alpaca controlled PAPER probe report to {output}")

    return 0 if report.result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
