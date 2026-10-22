"""Run the real Alpaca PAPER qualification harness for the PyTradeKit v0.5.0 gate."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast

from alpaca.trading.models import Asset

from pytradekit.brokers.adapters.alpaca import (
    AlpacaPaperOrderProbeConfig,
    build_alpaca_paper_order_probe,
    build_alpaca_paper_runtime,
    build_alpaca_paper_runtime_system,
)
from pytradekit.brokers.adapters.alpaca.production import (
    QualifiedAlpacaPaperRuntime,
    build_qualified_alpaca_paper_runtime,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.runtime import EnvironmentSecrets, RuntimeProfile, SystemClock
from pytradekit.runtime.qualification import (
    ProductionQualificationEvidence,
    QualificationStatus,
    evaluate_v050_release,
)
from pytradekit.shared import InstrumentId

_ACCOUNT_ID_ENV = "PYTRADEKIT_QUALIFICATION_ACCOUNT_ID"
_INSTRUMENT_ID_ENV = "PYTRADEKIT_QUALIFICATION_INSTRUMENT_ID"
_SYMBOL_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_SYMBOL"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify the PyTradeKit 0.5 runtime against a dedicated Alpaca PAPER account. "
            "There is no LIVE mode. PAPER orders are created only with --with-orders and "
            "the existing explicit order-probe acknowledgement environment variable."
        )
    )
    parser.add_argument(
        "--with-orders",
        action="store_true",
        help="Run controlled MARKET, LIMIT, CANCEL, recovery, and cleanup PAPER operations.",
    )
    parser.add_argument(
        "--ci-qualified",
        action="store_true",
        help="Record the current CI deterministic qualification gates as PASS.",
    )
    parser.add_argument(
        "--runbook-reviewed",
        action="store_true",
        help="Record operator review of the v0.5 incident/release runbooks as PASS.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Sanitized JSON qualification report path.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        profile = RuntimeProfile.alpaca_paper_from_environment()
        account_id = AccountId.from_string(_required_env(_ACCOUNT_ID_ENV))
        instrument_id = InstrumentId.from_string(_required_env(_INSTRUMENT_ID_ENV))
        symbol = os.environ.get(_SYMBOL_ENV, "AAPL").strip().upper()
        if not symbol:
            raise ValueError(f"{_SYMBOL_ENV} must not be empty.")
    except Exception as exc:
        print(f"Qualification configuration error: {exc}", file=sys.stderr)
        return 2

    paper_order_report: dict[str, object] | None = None
    order_probe_status = QualificationStatus.PENDING
    trade_updates_status = QualificationStatus.PENDING
    uncertain_status = QualificationStatus.PENDING
    cleanup_status = QualificationStatus.PENDING

    if args.with_orders:
        try:
            probe = build_alpaca_paper_order_probe(
                AlpacaPaperOrderProbeConfig.from_environment()
            ).run()
            paper_order_report = probe.to_dict()
            order_probe_status = (
                QualificationStatus.PASS
                if probe.result == "PASS"
                else QualificationStatus.FAIL
            )
            event_count_value = probe.stream.get("event_count")
            event_count = (
                event_count_value
                if type(event_count_value) is int
                else 0
            )
            trade_updates_status = (
                QualificationStatus.PASS
                if event_count > 0
                else QualificationStatus.FAIL
            )
            recovery = probe.uncertain_recovery
            uncertain_status = (
                QualificationStatus.PASS
                if (
                    recovery.get("simulated_post_ack_response_loss") is True
                    and recovery.get("resubmitted") is False
                    and recovery.get("submit_attempts") == 1
                )
                else QualificationStatus.FAIL
            )
            cleanup_status = (
                QualificationStatus.PASS
                if probe.baseline_position_qty == probe.final_position_qty
                else QualificationStatus.FAIL
            )
        except Exception as exc:
            print(
                "Controlled PAPER order qualification failed "
                f"({type(exc).__name__}). Inspect the PAPER account before retrying.",
                file=sys.stderr,
            )
            order_probe_status = QualificationStatus.FAIL
            trade_updates_status = QualificationStatus.FAIL
            uncertain_status = QualificationStatus.FAIL
            cleanup_status = QualificationStatus.FAIL

    runtime_runs: list[dict[str, object]] = []
    runtime_status = QualificationStatus.FAIL

    try:
        first = _run_runtime_cycle(
            profile=profile,
            account_id=account_id,
            instrument_id=instrument_id,
            symbol=symbol,
        )
        runtime_runs.append(first)

        second = _run_runtime_cycle(
            profile=profile,
            account_id=account_id,
            instrument_id=instrument_id,
            symbol=symbol,
        )
        runtime_runs.append(second)

        runtime_status = (
            QualificationStatus.PASS
            if all(
                bool(run["trading_ready"])
                and bool(run["shutdown_drained"])
                for run in runtime_runs
            )
            else QualificationStatus.FAIL
        )
    except Exception as exc:
        runtime_runs.append(
            {
                "trading_ready": False,
                "shutdown_drained": False,
                "error_type": type(exc).__name__,
            }
        )
        print(
            "Real PAPER runtime start/restart qualification failed "
            f"({type(exc).__name__}).",
            file=sys.stderr,
        )

    ci_status = (
        QualificationStatus.PASS
        if args.ci_qualified
        else QualificationStatus.PENDING
    )
    runbook_status = (
        QualificationStatus.PASS
        if args.runbook_reviewed
        else QualificationStatus.PENDING
    )

    evidence = ProductionQualificationEvidence(
        ci_quality_gate=ci_status,
        postgres_restart_e2e=ci_status,
        crash_window_faults=ci_status,
        graceful_shutdown=ci_status,
        provider_429_5xx_semantics=ci_status,
        real_paper_runtime_start_restart=runtime_status,
        real_paper_market_limit_cancel=order_probe_status,
        real_paper_trade_updates=trade_updates_status,
        real_paper_uncertain_recovery=uncertain_status,
        real_paper_cleanup=cleanup_status,
        incident_runbook=runbook_status,
    )
    release = evaluate_v050_release(evidence)

    payload = {
        "environment": "PAPER",
        "profile": profile.name,
        "account": profile.masked_account_id,
        "symbol": symbol,
        "runtime_runs": runtime_runs,
        "controlled_order_probe": paper_order_report,
        "release_gate": release.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote sanitized v0.5.0 qualification report to {args.output}")

    return 0 if release.release_ready else 1


def _run_runtime_cycle(
    *,
    profile: RuntimeProfile,
    account_id: AccountId,
    instrument_id: InstrumentId,
    symbol: str,
) -> dict[str, object]:
    composition = build_alpaca_paper_runtime(
        profile,
        EnvironmentSecrets(),
    )
    runtime: QualifiedAlpacaPaperRuntime | None = None
    try:
        asset = cast(Asset, composition.read_client.get_asset(symbol))
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
        shutdown = runtime.stop(timeout=10.0)
        return {
            "trading_ready": readiness.trading_ready,
            "readiness": readiness.to_dict(),
            "shutdown_drained": shutdown.drained,
            "shutdown_forced": shutdown.forced,
            "metrics": {
                "counters": runtime.observer.metrics.snapshot().counters,
                "gauges": runtime.observer.metrics.snapshot().gauges,
            },
        }
    finally:
        if runtime is not None and runtime.supervisor.gate.state.value != "STOPPED":
            runtime.stop(timeout=2.0)
        composition.engine.dispose()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
