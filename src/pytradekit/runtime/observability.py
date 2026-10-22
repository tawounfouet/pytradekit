"""Dependency-free operational metrics and structured audit events."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RuntimeMetricsSnapshot:
    """Immutable copy of runtime counters and gauges."""

    counters: dict[str, int]
    gauges: dict[str, int]


class RuntimeMetrics:
    """Thread-safe dependency-free metrics registry."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment one non-negative counter."""

        key = _metric_name(name)
        if type(amount) is not int or amount < 0:
            raise ValueError("Metric counter increment must be a non-negative integer.")
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def set_gauge(self, name: str, value: int) -> None:
        """Set one integer gauge."""

        key = _metric_name(name)
        if type(value) is not int:
            raise ValueError("Metric gauge value must be an integer.")
        with self._lock:
            self._gauges[key] = value

    def snapshot(self) -> RuntimeMetricsSnapshot:
        """Return a detached metrics snapshot."""

        with self._lock:
            return RuntimeMetricsSnapshot(
                counters=dict(self._counters),
                gauges=dict(self._gauges),
            )


@dataclass(frozen=True, slots=True)
class OperationalEvent:
    """Sanitized structured operational event."""

    name: str
    occurred_at: datetime
    fields: dict[str, str | int | bool | None]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe content."""

        return {
            "name": self.name,
            "occurred_at": self.occurred_at.isoformat(),
            "fields": dict(self.fields),
        }


class OperationalEventSink(Protocol):
    """Emit one sanitized operational event."""

    def emit(self, event: OperationalEvent) -> None:
        """Persist or forward one event."""

        ...


class NullOperationalEventSink:
    """Production-safe no-op event sink."""

    def emit(self, event: OperationalEvent) -> None:
        """Ignore the event."""

        _ = event


class InMemoryOperationalEventSink:
    """Collect operational events for tests and local diagnostics."""

    def __init__(self) -> None:
        self.events: list[OperationalEvent] = []

    def emit(self, event: OperationalEvent) -> None:
        """Append one event."""

        self.events.append(event)


class JsonLinesOperationalEventSink:
    """Append sanitized operational events as JSON lines."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def emit(self, event: OperationalEvent) -> None:
        """Append one JSON object and create parent directories when necessary."""

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")


class RuntimeObserver:
    """Small facade combining metrics and structured operational events."""

    def __init__(
        self,
        *,
        metrics: RuntimeMetrics | None = None,
        sink: OperationalEventSink | None = None,
    ) -> None:
        self.metrics = metrics or RuntimeMetrics()
        self._sink = sink or NullOperationalEventSink()

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment one metric."""

        self.metrics.increment(name, amount)

    def set_gauge(self, name: str, value: int) -> None:
        """Set one gauge."""

        self.metrics.set_gauge(name, value)

    def event(
        self,
        name: str,
        **fields: str | int | bool | None,
    ) -> None:
        """Emit one structured event after rejecting secret-like field names."""

        _validate_safe_fields(fields)
        event = OperationalEvent(
            name=_metric_name(name),
            occurred_at=datetime.now(UTC),
            fields=dict(fields),
        )
        self._sink.emit(event)


def _metric_name(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError("Metric or event name must be a non-empty string.")
    return normalized


def _validate_safe_fields(fields: Mapping[str, object]) -> None:
    forbidden_fragments = (
        "secret",
        "password",
        "api_key",
        "apikey",
        "token",
        "credential",
    )
    for name in fields:
        lowered = name.lower()
        if any(fragment in lowered for fragment in forbidden_fragments):
            raise ValueError(
                f"Operational field {name!r} is forbidden because it may expose secrets."
            )
