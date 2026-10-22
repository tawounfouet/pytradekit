"""In-memory and runtime-observer alert adapters."""

from copy import deepcopy

from pytradekit.operations.domain import Alert, AlertId
from pytradekit.operations.ports import AlertDeliveryResult, AlertSinkPort
from pytradekit.runtime.observability import RuntimeObserver


class InMemoryAlertRepository:
    """Stateful alert repository for single-process P0 operation and tests."""

    def __init__(self) -> None:
        self._alerts: dict[AlertId, Alert] = {}

    def get(self, alert_id: AlertId) -> Alert | None:
        alert = self._alerts.get(alert_id)
        return deepcopy(alert) if alert is not None else None

    def find_unresolved_by_deduplication_key(
        self,
        deduplication_key: str,
    ) -> Alert | None:
        matches = [
            alert
            for alert in self._alerts.values()
            if alert.deduplication_key == deduplication_key and alert.unresolved
        ]
        if not matches:
            return None
        alert = min(matches, key=lambda item: item.created_at)
        return deepcopy(alert)

    def list_open(self) -> tuple[Alert, ...]:
        return tuple(
            deepcopy(alert)
            for alert in sorted(
                (item for item in self._alerts.values() if item.unresolved),
                key=lambda item: (item.created_at, str(item.id)),
            )
        )

    def save(self, alert: Alert) -> None:
        self._alerts[alert.id] = deepcopy(alert)


class InMemoryAlertSink:
    """Collect delivered alerts."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def deliver(self, alert: Alert) -> None:
        self.alerts.append(deepcopy(alert))


class FailingAlertSink:
    """Deterministic sink failure for qualification."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RuntimeError("alert sink unavailable")

    def deliver(self, alert: Alert) -> None:
        _ = alert
        raise self._error


class RuntimeAlertSink:
    """Emit sanitized alert delivery through the existing event channel."""

    def __init__(self, observer: RuntimeObserver) -> None:
        self._observer = observer

    def deliver(self, alert: Alert) -> None:
        self._observer.event(
            "AlertRaised",
            alert_type=alert.type.value,
            severity=alert.severity.value,
            state=alert.state.value,
            title=alert.title,
        )


class DefaultAlertRouter:
    """Route to every sink and report bounded failures without raising."""

    def __init__(self, sinks: tuple[AlertSinkPort, ...]) -> None:
        self._sinks = sinks

    def route(self, alert: Alert) -> AlertDeliveryResult:
        delivered = 0
        failures: list[str] = []
        for sink in self._sinks:
            try:
                sink.deliver(alert)
            except Exception as exc:
                failures.append(type(exc).__name__)
            else:
                delivered += 1
        return AlertDeliveryResult(
            attempted=len(self._sinks),
            delivered=delivered,
            failure_types=tuple(failures),
        )
