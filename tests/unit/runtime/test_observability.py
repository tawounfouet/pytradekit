"""Unit tests for production runtime observability primitives."""

from pathlib import Path

import pytest

from pytradekit.runtime.observability import (
    InMemoryOperationalEventSink,
    JsonLinesOperationalEventSink,
    RuntimeMetrics,
    RuntimeObserver,
)


def test_metrics_are_thread_safe_api_and_snapshot_is_detached() -> None:
    metrics = RuntimeMetrics()

    metrics.increment("trade_updates_received")
    metrics.increment("trade_updates_received", 2)
    metrics.set_gauge("trading_ready", 1)

    snapshot = metrics.snapshot()

    assert snapshot.counters["trade_updates_received"] == 3
    assert snapshot.gauges["trading_ready"] == 1

    metrics.increment("trade_updates_received")
    assert snapshot.counters["trade_updates_received"] == 3


def test_observer_rejects_secret_like_field_names() -> None:
    observer = RuntimeObserver()

    with pytest.raises(ValueError, match="forbidden"):
        observer.event("unsafe", api_key="should-never-be-emitted")


def test_in_memory_operational_events_are_structured() -> None:
    sink = InMemoryOperationalEventSink()
    observer = RuntimeObserver(sink=sink)

    observer.event("runtime_not_ready", gap_count=2)

    assert len(sink.events) == 1
    assert sink.events[0].name == "runtime_not_ready"
    assert sink.events[0].fields == {"gap_count": 2}


def test_json_lines_sink_writes_one_object_per_event(tmp_path: Path) -> None:
    path = tmp_path / "runtime.jsonl"
    observer = RuntimeObserver(
        sink=JsonLinesOperationalEventSink(path)
    )

    observer.event("runtime_started", environment="PAPER")
    observer.event("runtime_stopped", drained=True)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"name": "runtime_started"' in lines[0]
    assert '"name": "runtime_stopped"' in lines[1]
