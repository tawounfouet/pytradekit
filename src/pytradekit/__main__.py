"""Command-line entry point for PyTradeKit."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pytradekit import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the minimal bootstrap command-line parser."""
    parser = argparse.ArgumentParser(prog="pytradekit")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PyTradeKit bootstrap CLI."""
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
