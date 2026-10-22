"""PyTradeKit 0.5 Alpaca PAPER runtime demonstration.

The example is safe by default. Running it without --run-real-paper performs
no broker call, no database connection, and no economic order.

The opt-in path starts the real Alpaca PAPER runtime, performs startup
reconciliation and private stream readiness, then shuts down gracefully.
It does not submit or cancel provider orders.
"""

from __future__ import annotations

import argparse
import os
from typing import Any


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Demonstrate the PyTradeKit 0.5 Alpaca PAPER runtime. "
            "The default mode is safe and infrastructure-free."
        )
    )
    parser.add_argument(
        "--run-real-paper",
        action="store_true",
        help=(
            "Opt in to the real Alpaca PAPER startup/reconciliation path. "
            "Requires the Alpaca and PostgreSQL extras plus configured environment."
        ),
    )
    return parser


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required for --run-real-paper.")
    return value


def _print_safe_overview() -> None:
    print("PyTradeKit 0.5 Alpaca PAPER runtime example")
    print("mode: safe overview")
    print("provider calls: none")
    print("database calls: none")
    print("economic orders: none")
    print("")
    print("0.5 runtime flow:")
    print("configuration -> PostgreSQL -> Alpaca PAPER -> reconciliation")
    print("-> private trade_updates -> TRADING_READY -> graceful shutdown")
    print("")
    print("To run the real PAPER startup path explicitly:")
    print("python examples/07_alpaca_paper_runtime.py --run-real-paper")
    print("")
    print("See docs/runbooks/PYTRADEKIT_0_5_RELEASE_QUALIFICATION.md")
    print("for required environment variables and dedicated account guidance.")


def _run_real_paper() -> int:
    # Deferred imports keep the default release smoke test free of optional
    # Alpaca and PostgreSQL runtime dependencies.
    from alpaca.trading.models import Asset

    from pytradekit.brokers.adapters.alpaca import (
        build_alpaca_paper_runtime,
        build_alpaca_paper_runtime_system,
        build_qualified_alpaca_paper_runtime,
    )
    from pytradekit.portfolio.domain import AccountId
    from pytradekit.reference.domain import InstrumentMapping
    from pytradekit.runtime import EnvironmentSecrets, RuntimeProfile, SystemClock
    from pytradekit.shared import InstrumentId

    profile = RuntimeProfile.alpaca_paper_from_environment()
    account_id = AccountId.from_string(
        _required_env("PYTRADEKIT_QUALIFICATION_ACCOUNT_ID")
    )
    instrument_id = InstrumentId.from_string(
        _required_env("PYTRADEKIT_QUALIFICATION_INSTRUMENT_ID")
    )
    symbol = os.environ.get("PYTRADEKIT_ALPACA_ORDER_PROBE_SYMBOL", "AAPL")
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("PYTRADEKIT_ALPACA_ORDER_PROBE_SYMBOL must not be empty.")

    composition = build_alpaca_paper_runtime(profile, EnvironmentSecrets())
    runtime: Any | None = None

    try:
        asset = composition.read_client.get_asset(symbol)
        if not isinstance(asset, Asset):
            raise RuntimeError("Alpaca asset response has an unexpected type.")

        mapping = InstrumentMapping(
            instrument_id=instrument_id,
            provider="alpaca",
            external_symbol=symbol,
            external_id=str(asset.id),
        )
        system = build_alpaca_paper_runtime_system(
            composition=composition,
            mappings=(mapping,),
            account_id=account_id,
            clock=SystemClock(),
        )
        runtime = build_qualified_alpaca_paper_runtime(system)

        readiness = runtime.start()
        print(f"provider: {profile.provider}")
        print(f"environment: {profile.environment.value}")
        print(f"account: {profile.masked_account_id}")
        print(f"symbol: {symbol}")
        print(f"trading_ready: {readiness.trading_ready}")

        shutdown = runtime.stop(timeout=10.0)
        print(f"shutdown_drained: {shutdown.drained}")
        print(f"shutdown_forced: {shutdown.forced}")

        return 0 if readiness.trading_ready and shutdown.drained else 1
    finally:
        if runtime is not None and runtime.supervisor.gate.state.value != "STOPPED":
            runtime.stop(timeout=2.0)
        composition.engine.dispose()


def main() -> int:
    args = _parser().parse_args()
    if not args.run_real_paper:
        _print_safe_overview()
        return 0
    return _run_real_paper()


if __name__ == "__main__":
    raise SystemExit(main())
