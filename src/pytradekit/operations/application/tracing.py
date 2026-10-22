"""Fail-safe tracing around application operations."""

from collections.abc import Callable
from typing import TypeVar

from pytradekit.operations.domain import TraceContext, TraceRecord
from pytradekit.operations.ports import TraceExporterPort
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.runtime.ports import ClockPort

T = TypeVar("T")


class TraceRecorder:
    """Execute an operation and export tracing without owning its outcome."""

    def __init__(
        self,
        *,
        exporter: TraceExporterPort,
        clock: ClockPort,
        observer: RuntimeObserver | None = None,
    ) -> None:
        self._exporter = exporter
        self._clock = clock
        self._observer = observer or RuntimeObserver()

    def observe(
        self,
        *,
        name: str,
        context: TraceContext,
        operation: Callable[[], T],
    ) -> T:
        started_at = self._clock.now()
        try:
            return operation()
        finally:
            record = TraceRecord(
                name=name,
                context=context,
                started_at=started_at,
                finished_at=self._clock.now(),
            )
            try:
                self._exporter.export(record)
            except Exception as exc:
                self._observer.increment("telemetry_export_failures_total")
                self._observer.event(
                    "TelemetryExportFailed",
                    error_type=type(exc).__name__,
                )
