"""Trace exporters including an OpenTelemetry-compatible adapter."""

from typing import Protocol

from pytradekit.operations.domain import TraceRecord


class _OpenTelemetrySpanLike(Protocol):
    def set_attribute(
        self,
        key: str,
        value: str | int | bool,
    ) -> object:
        ...

    def end(self) -> object:
        ...


class _OpenTelemetryTracerLike(Protocol):
    def start_span(self, name: str) -> _OpenTelemetrySpanLike:
        ...


class InMemoryTraceExporter:
    """Collect trace records for tests and local diagnostics."""

    def __init__(self) -> None:
        self.records: list[TraceRecord] = []

    def export(self, record: TraceRecord) -> None:
        self.records.append(record)


class OpenTelemetryTraceAdapter:
    """Map TraceRecord to an injected OpenTelemetry-compatible tracer."""

    def __init__(self, tracer: _OpenTelemetryTracerLike) -> None:
        self._tracer = tracer

    def export(self, record: TraceRecord) -> None:
        span = self._tracer.start_span(record.name)
        if record.context.correlation_id is not None:
            span.set_attribute(
                "pytradekit.correlation_id",
                str(record.context.correlation_id),
            )
        if record.context.causation_id is not None:
            span.set_attribute(
                "pytradekit.causation_id",
                str(record.context.causation_id),
            )
        for key, value in record.context.attributes.items():
            if value is not None:
                span.set_attribute(f"pytradekit.{key}", value)
        span.end()
