"""LOT-07 bounded startup and shutdown telemetry qualification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event

import pytest

from pytradekit.runtime import ReadinessCheck, ReadinessCheckStatus
from pytradekit.runtime.errors import RuntimeStartupTimeoutError
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.runtime.operations import (
    ProductionRuntimeSupervisor,
    RuntimeLifecycleState,
)
from pytradekit.runtime.trading_readiness import TradingReadinessReport

NOW = datetime(2026, 10, 22, 22, 30, tzinfo=UTC)


@dataclass
class _BlockingRuntime:
    release: Event
    stops: int = 0

    def start(self) -> TradingReadinessReport:
        self.release.wait(timeout=2)
        return TradingReadinessReport(
            provider="alpaca",
            environment="PAPER",
            account="********1234",
            checks=(ReadinessCheck("ready", ReadinessCheckStatus.PASS, "ok"),),
        )

    def stop(self) -> None:
        self.stops += 1


class _BlockingFlusher:
    def __init__(self) -> None:
        self.release = Event()

    def flush(self) -> None:
        self.release.wait(timeout=2)


def test_startup_timeout_never_opens_late_admission() -> None:
    runtime = _BlockingRuntime(release=Event())
    supervisor = ProductionRuntimeSupervisor(runtime=runtime)

    with pytest.raises(RuntimeStartupTimeoutError):
        supervisor.start(timeout=0.01)

    assert supervisor.gate.state is RuntimeLifecycleState.DEGRADED

    runtime.release.set()

    assert supervisor.gate.state is RuntimeLifecycleState.DEGRADED
    assert supervisor.observer.metrics.snapshot().gauges["trading_ready"] == 0


def test_shutdown_telemetry_flush_is_bounded_and_non_blocking_to_safety() -> None:
    runtime = _BlockingRuntime(release=Event())
    runtime.release.set()
    flusher = _BlockingFlusher()
    observer = RuntimeObserver()
    supervisor = ProductionRuntimeSupervisor(
        runtime=runtime,
        observer=observer,
        telemetry_flusher=flusher,
    )
    supervisor.start()

    report = supervisor.shutdown(
        timeout=0.1,
        telemetry_flush_timeout=0.01,
    )

    assert report.final_state is RuntimeLifecycleState.STOPPED
    assert report.telemetry_flushed is False
    assert observer.metrics.snapshot().counters[
        "telemetry_flush_failures_total"
    ] == 1
    flusher.release.set()
