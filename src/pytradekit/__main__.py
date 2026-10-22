"""Command-line entry point for PyTradeKit."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from pytradekit import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the deployment-aware command-line parser."""

    parser = argparse.ArgumentParser(prog="pytradekit")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subcommands = parser.add_subparsers(dest="command")

    subcommands.add_parser("liveness", help="Print process liveness JSON.")

    health = subcommands.add_parser(
        "health",
        help="Run a sanitized deployment readiness preflight.",
    )
    health.add_argument(
        "--local-development",
        action="store_true",
        help="Allow local PostgreSQL without TLS.",
    )

    server = subcommands.add_parser(
        "serve-health",
        help="Serve read-only /health/live and /health/ready endpoints.",
    )
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8080)
    server.add_argument(
        "--local-development",
        action="store_true",
        help="Allow local PostgreSQL without TLS.",
    )
    return parser


def _build_preflight(*, local_development: bool):
    from pytradekit.runtime import RuntimeProfile, RuntimeSecurityConfig
    from pytradekit.runtime.adapters import build_default_secrets
    from pytradekit.runtime.deployment import DeploymentPreflight

    profile = RuntimeProfile.alpaca_paper_from_environment()
    file_root = Path(
        os.environ.get("PYTRADEKIT_SECRET_FILE_ROOT", "/run/secrets")
    )
    security = (
        RuntimeSecurityConfig.local_development()
        if local_development
        else RuntimeSecurityConfig.production_like()
    )
    return DeploymentPreflight(
        profile=profile,
        secrets=build_default_secrets(file_root=file_root),
        security=security,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PyTradeKit operational CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        return 0

    if args.command == "liveness":
        print(
            json.dumps(
                {
                    "live": True,
                    "ready": False,
                    "trading_ready": False,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "health":
        report = _build_preflight(
            local_development=bool(args.local_development)
        ).readiness()
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0 if report.ready else 1

    if args.command == "serve-health":
        from pytradekit.runtime.deployment import serve_health

        preflight = _build_preflight(
            local_development=bool(args.local_development)
        )
        serve_health(
            preflight=preflight,
            host=str(args.host),
            port=int(args.port),
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
