"""Unit qualification for trace propagation and exporter isolation."""

from datetime import UTC, datetime

from pytradekit.operations import TraceContext
from pytradekit.operations.adapters import (
    InMemoryTraceExporter,
    OpenTelemetryTraceAdapter,
)
from pytradekit.operations.application import TraceRecorder
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.shared import CausationId, CorrelationId
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 21, 10, tzinfo=UTC)


class _FailingExporter:
    def export(self, record) -> None:
        _ = record
        raise RuntimeError("telemetry backend unavailable")


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, str | int | bool] = {}
        self.ended = False

    def set_attribute(
        self,
        key: str,
        value: str | int | bool,
    ) -> object:
        self.attributes[key] = value
        return None

    def end(self) -> object:
        self.ended = True
        return None


class _Tracer:
    def __init__(self) -> None:
        self.name: str | None = None
        self.span = _Span()

    def start_span(self, name: str) -> _Span:
        self.name = name
        return self.span


def test_trace_context_preserves_business_correlation_and_causation() -> None:
    exporter = InMemoryTraceExporter()
    correlation_id = CorrelationId.new()
    causation_id = CausationId.new()
    result = TraceRecorder(
        exporter=exporter,
        clock=FakeClock.at(NOW),
    ).observe(
        name="submit_order",
        context=TraceContext(
            correlation_id=correlation_id,
            causation_id=causation_id,
            attributes={"environment": "PAPER"},
        ),
        operation=lambda: "ok",
    )

    assert result == "ok"
    assert exporter.records[0].context.correlation_id == correlation_id
    assert exporter.records[0].context.causation_id == causation_id


def test_exporter_failure_does_not_change_application_result() -> None:
    observer = RuntimeObserver()
    result = TraceRecorder(
        exporter=_FailingExporter(),
        clock=FakeClock.at(NOW),
        observer=observer,
    ).observe(
        name="application_command",
        context=TraceContext(attributes={"environment": "PAPER"}),
        operation=lambda: 42,
    )

    assert result == 42
    assert observer.metrics.snapshot().counters[
        "telemetry_export_failures_total"
    ] == 1


def test_opentelemetry_adapter_maps_business_ids_to_span_attributes() -> None:
    tracer = _Tracer()
    correlation_id = CorrelationId.new()
    exporter = OpenTelemetryTraceAdapter(tracer)
    TraceRecorder(
        exporter=exporter,
        clock=FakeClock.at(NOW),
    ).observe(
        name="authorize",
        context=TraceContext(
            correlation_id=correlation_id,
            attributes={"environment": "PAPER"},
        ),
        operation=lambda: None,
    )

    assert tracer.name == "authorize"
    assert tracer.span.attributes["pytradekit.correlation_id"] == str(
        correlation_id
    )
    assert tracer.span.attributes["pytradekit.environment"] == "PAPER"
    assert tracer.span.ended
