"""Fail a release pipeline unless a v0.5.0 qualification report is release-ready."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a sanitized PyTradeKit v0.5.0 production qualification report."
    )
    parser.add_argument(
        "report",
        type=Path,
        help="JSON report produced by alpaca_paper_v050_qualification.py.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        payload = json.loads(args.report.read_text(encoding="utf-8"))
        release = payload["release_gate"]
        release_ready = bool(release["release_ready"])
        pending = release.get("pending_required", [])
        failed = release.get("failed_required", [])
    except Exception as exc:
        print(
            f"Invalid qualification report ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    if release_ready:
        print("PyTradeKit v0.5.0 production qualification gate: PASS")
        return 0

    print("PyTradeKit v0.5.0 production qualification gate: BLOCKED", file=sys.stderr)
    if pending:
        print(f"Pending required gates: {', '.join(map(str, pending))}", file=sys.stderr)
    if failed:
        print(f"Failed required gates: {', '.join(map(str, failed))}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
