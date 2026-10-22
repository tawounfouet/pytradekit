"""Unit qualification for stateful operational alerts."""

from datetime import UTC, datetime

import pytest

from pytradekit.operations import (
    AlertSeverity,
    AlertState,
    AlertType,
)
from pytradekit.operations.adapters import (
    DefaultAlertRouter,
    FailingAlertSink,
    InMemoryAlertRepository,
    InMemoryAlertSink,
)
from pytradekit.operations.application import (
    AcknowledgeAlert,
    ListOpenAlerts,
    RaiseAlert,
    ResolveAlert,
)
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 21, 10, tzinfo=UTC)


def test_repeated_condition_reuses_one_unresolved_alert() -> None:
    repository = InMemoryAlertRepository()
    sink = InMemoryAlertSink()
    raise_alert = RaiseAlert(
        repository=repository,
        router=DefaultAlertRouter((sink,)),
        clock=FakeClock.at(NOW),
    )

    first = raise_alert.execute(
        alert_type=AlertType.DATABASE_UNAVAILABLE,
        severity=AlertSeverity.CRITICAL,
        title="Database unavailable",
        reason="database probe failed",
        deduplication_key="health:DATABASE",
    )
    second = raise_alert.execute(
        alert_type=AlertType.DATABASE_UNAVAILABLE,
        severity=AlertSeverity.CRITICAL,
        title="Database unavailable",
        reason="database probe failed again",
        deduplication_key="health:DATABASE",
    )

    assert second.id == first.id
    assert len(repository.list_open()) == 1
    assert len(sink.alerts) == 1


def test_acknowledgement_does_not_resolve_alert() -> None:
    repository = InMemoryAlertRepository()
    alert = RaiseAlert(
        repository=repository,
        router=DefaultAlertRouter(()),
        clock=FakeClock.at(NOW),
    ).execute(
        alert_type=AlertType.BROKER_DISCONNECTED,
        severity=AlertSeverity.HIGH,
        title="Broker disconnected",
        reason="stream unavailable",
        deduplication_key="health:BROKER_STREAM",
    )

    acknowledged = AcknowledgeAlert(
        repository=repository,
        clock=FakeClock.at(NOW),
    ).execute(alert.id)

    assert acknowledged.state is AlertState.ACKNOWLEDGED
    assert ListOpenAlerts(repository).execute() == (acknowledged,)


def test_resolution_requires_verified_clear_condition() -> None:
    repository = InMemoryAlertRepository()
    alert = RaiseAlert(
        repository=repository,
        router=DefaultAlertRouter(()),
        clock=FakeClock.at(NOW),
    ).execute(
        alert_type=AlertType.RECONCILIATION_FAILED,
        severity=AlertSeverity.HIGH,
        title="Reconciliation unhealthy",
        reason="last run failed",
        deduplication_key="health:RECONCILIATION",
    )
    resolver = ResolveAlert(
        repository=repository,
        clock=FakeClock.at(NOW),
    )

    with pytest.raises(ValueError, match="verified_clear"):
        resolver.execute(alert.id, verified_clear=False)

    resolved = resolver.execute(alert.id, verified_clear=True)
    assert resolved.state is AlertState.RESOLVED
    assert repository.list_open() == ()


def test_sink_failure_keeps_alert_open_and_records_failure_metric() -> None:
    repository = InMemoryAlertRepository()
    observer = RuntimeObserver()
    alert = RaiseAlert(
        repository=repository,
        router=DefaultAlertRouter((FailingAlertSink(),)),
        clock=FakeClock.at(NOW),
        observer=observer,
    ).execute(
        alert_type=AlertType.DATABASE_UNAVAILABLE,
        severity=AlertSeverity.CRITICAL,
        title="Database unavailable",
        reason="database probe failed",
        deduplication_key="health:DATABASE",
    )

    assert repository.get(alert.id) == alert
    assert alert.state is AlertState.OPEN
    snapshot = observer.metrics.snapshot()
    assert (
        snapshot.counters[
            "alert_delivery_failures_total{alert_type=DATABASE_UNAVAILABLE,"
            "severity=CRITICAL}"
        ]
        == 1
    )
