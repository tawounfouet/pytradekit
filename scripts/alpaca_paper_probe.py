"""Run the PyTradeKit Alpaca PAPER read-only discovery probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pytradekit.brokers.adapters.alpaca import (
    AlpacaPaperProbeConfig,
    build_alpaca_paper_probe,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Alpaca PAPER probe. Credentials are read from environment variables; "
            "this command has no LIVE mode and exposes no trading command."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Defaults to stdout.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        config = AlpacaPaperProbeConfig.from_environment()
        report = build_alpaca_paper_probe(config).run()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - real provider boundary
        print(
            "Alpaca PAPER read-only probe failed "
            f"({type(exc).__name__}). No provider write command is exposed by this probe.",
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
        print(f"Wrote sanitized Alpaca PAPER probe report to {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
