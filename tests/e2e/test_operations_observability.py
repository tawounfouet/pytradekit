"""End-to-end LOT-06 metrics, tracing, and alerting qualification."""

from datetime import UTC, datetime

from pytradekit.operations import (
    AlertState,
    AlertType,
    HealthComponent,
    HealthReport,
    HealthSnapshot,
    HealthStatus,
    TraceContext,
    TraceRecord,
)
from pytradekit.operations.adapters import (
    DefaultAlertRouter,
    FailingAlertSink,
    InMemoryAlertRepository,
    InMemoryAlertSink,
)
from pytradekit.operations.application import (
    OperationalAlertEvaluator,
    RaiseAlert,
    ResolveAlert,
    TraceRecorder,
)
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 21, 10, tzinfo=UTC)


class _FailingTraceExporter:
    def export(self, record: TraceRecord) -> None:
        _ = record
        raise RuntimeError("collector unavailable")


def _evaluator(
    *,
    repository: InMemoryAlertRepository,
    observer: RuntimeObserver,
    failing_sink: bool = False,
) -> OperationalAlertEvaluator:
    sinks = (
        (FailingAlertSink(),)
        if failing_sink
        else (InMemoryAlertSink(),)
    )
    raise_alert = RaiseAlert(
        repository=repository,
        router=DefaultAlertRouter(sinks),
        clock=FakeClock.at(NOW),
        observer=observer,
    )
    return OperationalAlertEvaluator(
        repository=repository,
        raise_alert=raise_alert,
        resolve_alert=ResolveAlert(
            repository=repository,
            clock=FakeClock.at(NOW),
            observer=observer,
        ),
    )


def test_database_failure_generates_one_open_alert_even_if_sink_fails() -> None:
    repository = InMemoryAlertRepository()
    observer = RuntimeObserver()
    evaluator = _evaluator(
        repository=repository,
        observer=observer,
        failing_sink=True,
    )
    snapshot = HealthSnapshot(
        reports=(
            HealthReport(
                component=HealthComponent.DATABASE,
                status=HealthStatus.UNHEALTHY,
                observed_at=NOW,
                message="database probe failed",
            ),
        ),
        observed_at=NOW,
    )

    first = evaluator.evaluate_health(snapshot)
    second = evaluator.evaluate_health(snapshot)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id
    assert repository.list_open()[0].state is AlertState.OPEN
    assert repository.list_open()[0].type is AlertType.DATABASE_UNAVAILABLE
    counters = observer.metrics.snapshot().counters
    assert counters["alerts_deduplicated_total"] == 1
    assert (
        counters[
            "alert_delivery_failures_total{alert_type=DATABASE_UNAVAILABLE,"
            "severity=CRITICAL}"
        ]
        == 1
    )


def test_broker_stream_loss_alert_resolves_when_health_is_verified_healthy() -> None:
    repository = InMemoryAlertRepository()
    observer = RuntimeObserver()
    evaluator = _evaluator(repository=repository, observer=observer)
    unhealthy = HealthSnapshot(
        reports=(
            HealthReport(
                component=HealthComponent.BROKER_STREAM,
                status=HealthStatus.UNHEALTHY,
                observed_at=NOW,
                message="private stream lost",
            ),
        ),
        observed_at=NOW,
    )
    healthy = HealthSnapshot(
        reports=(
            HealthReport(
                component=HealthComponent.BROKER_STREAM,
                status=HealthStatus.HEALTHY,
                observed_at=NOW,
                message="private stream restored",
                last_success_at=NOW,
            ),
        ),
        observed_at=NOW,
    )

    raised = evaluator.evaluate_health(unhealthy)[0]
    evaluator.evaluate_health(healthy)

    stored = repository.get(raised.id)
    assert stored is not None
    assert stored.state is AlertState.RESOLVED


def test_critical_mismatch_opens_one_critical_alert() -> None:
    repository = InMemoryAlertRepository()
    observer = RuntimeObserver()
    evaluator = _evaluator(repository=repository, observer=observer)

    first = evaluator.critical_mismatch(reason="position divergence")
    second = evaluator.critical_mismatch(reason="position divergence repeated")

    assert first.id == second.id
    assert first.type is AlertType.CRITICAL_MISMATCH
    assert first.state is AlertState.OPEN
    assert len(repository.list_open()) == 1


def test_telemetry_outage_does_not_change_core_operation_result() -> None:
    observer = RuntimeObserver()
    value = TraceRecorder(
        exporter=_FailingTraceExporter(),
        clock=FakeClock.at(NOW),
        observer=observer,
    ).observe(
        name="qualified-operation",
        context=TraceContext(attributes={"environment": "PAPER"}),
        operation=lambda: "economic-result",
    )

    assert value == "economic-result"
    assert observer.metrics.snapshot().counters[
        "telemetry_export_failures_total"
    ] == 1
