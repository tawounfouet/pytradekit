"""Stateful alert raising, deduplication, acknowledgement, and resolution."""

from pytradekit.operations.domain import (
    Alert,
    AlertId,
    AlertSeverity,
    AlertState,
    AlertType,
    HealthComponent,
    HealthSnapshot,
    HealthStatus,
)
from pytradekit.operations.ports import AlertRepositoryPort, AlertRouterPort
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import CorrelationId


class RaiseAlert:
    """Persist alert state before best-effort sink delivery."""

    def __init__(
        self,
        *,
        repository: AlertRepositoryPort,
        router: AlertRouterPort,
        clock: ClockPort,
        observer: RuntimeObserver | None = None,
    ) -> None:
        self._repository = repository
        self._router = router
        self._clock = clock
        self._observer = observer or RuntimeObserver()

    def execute(
        self,
        *,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        reason: str,
        deduplication_key: str,
        correlation_id: CorrelationId | None = None,
    ) -> Alert:
        existing = self._repository.find_unresolved_by_deduplication_key(
            deduplication_key
        )
        if existing is not None:
            self._observer.increment("alerts_deduplicated_total")
            return existing

        alert = Alert(
            id=AlertId.new(),
            type=alert_type,
            severity=severity,
            state=AlertState.OPEN,
            title=title,
            reason=reason,
            created_at=self._clock.now(),
            deduplication_key=deduplication_key,
            correlation_id=correlation_id,
        )
        self._repository.save(alert)
        self._observer.increment_labeled(
            "alerts_created_total",
            labels={
                "alert_type": alert_type.value,
                "severity": severity.value,
            },
        )
        result = self._router.route(alert)
        if result.failures:
            self._observer.increment_labeled(
                "alert_delivery_failures_total",
                labels={
                    "alert_type": alert_type.value,
                    "severity": severity.value,
                },
                amount=result.failures,
            )
            self._observer.event(
                "AlertDeliveryFailed",
                alert_type=alert_type.value,
                severity=severity.value,
                failure_count=result.failures,
            )
        return alert


class ListOpenAlerts:
    """List unresolved OPEN or ACKNOWLEDGED alerts."""

    def __init__(self, repository: AlertRepositoryPort) -> None:
        self._repository = repository

    def execute(self) -> tuple[Alert, ...]:
        return self._repository.list_open()


class AcknowledgeAlert:
    """Acknowledge without resolving the underlying condition."""

    def __init__(
        self,
        *,
        repository: AlertRepositoryPort,
        clock: ClockPort,
        observer: RuntimeObserver | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._observer = observer or RuntimeObserver()

    def execute(self, alert_id: AlertId) -> Alert:
        alert = self._repository.get(alert_id)
        if alert is None:
            raise KeyError(f"Alert {alert_id} was not found.")
        acknowledged = alert.acknowledge(occurred_at=self._clock.now())
        self._repository.save(acknowledged)
        self._observer.event(
            "AlertAcknowledged",
            alert_type=acknowledged.type.value,
            severity=acknowledged.severity.value,
        )
        return acknowledged


class ResolveAlert:
    """Resolve only after the underlying condition is verified clear."""

    def __init__(
        self,
        *,
        repository: AlertRepositoryPort,
        clock: ClockPort,
        observer: RuntimeObserver | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._observer = observer or RuntimeObserver()

    def execute(
        self,
        alert_id: AlertId,
        *,
        verified_clear: bool,
    ) -> Alert:
        if not verified_clear:
            raise ValueError("Alert resolution requires verified_clear=True.")
        alert = self._repository.get(alert_id)
        if alert is None:
            raise KeyError(f"Alert {alert_id} was not found.")
        resolved = alert.resolve(occurred_at=self._clock.now())
        self._repository.save(resolved)
        self._observer.increment_labeled(
            "alerts_resolved_total",
            labels={
                "alert_type": resolved.type.value,
                "severity": resolved.severity.value,
            },
        )
        self._observer.event(
            "AlertResolved",
            alert_type=resolved.type.value,
            severity=resolved.severity.value,
        )
        return resolved


class OperationalAlertEvaluator:
    """Translate verified operational conditions into stateful alerts."""

    def __init__(
        self,
        *,
        repository: AlertRepositoryPort,
        raise_alert: RaiseAlert,
        resolve_alert: ResolveAlert,
    ) -> None:
        self._repository = repository
        self._raise_alert = raise_alert
        self._resolve_alert = resolve_alert

    def evaluate_health(
        self,
        snapshot: HealthSnapshot,
        *,
        correlation_id: CorrelationId | None = None,
    ) -> tuple[Alert, ...]:
        alerts: list[Alert] = []
        conditions = (
            (
                HealthComponent.DATABASE,
                AlertType.DATABASE_UNAVAILABLE,
                AlertSeverity.CRITICAL,
                "Database unavailable",
            ),
            (
                HealthComponent.BROKER_STREAM,
                AlertType.BROKER_DISCONNECTED,
                AlertSeverity.HIGH,
                "Broker stream unavailable",
            ),
            (
                HealthComponent.RECONCILIATION,
                AlertType.RECONCILIATION_FAILED,
                AlertSeverity.HIGH,
                "Reconciliation unhealthy",
            ),
        )
        for component, alert_type, severity, title in conditions:
            report = snapshot.get(component)
            key = f"health:{component.value}"
            if report is not None and report.status in {
                HealthStatus.UNHEALTHY,
                HealthStatus.UNKNOWN,
            }:
                alerts.append(
                    self._raise_alert.execute(
                        alert_type=alert_type,
                        severity=severity,
                        title=title,
                        reason=report.message,
                        deduplication_key=key,
                        correlation_id=correlation_id,
                    )
                )
                continue
            existing = self._repository.find_unresolved_by_deduplication_key(key)
            if (
                existing is not None
                and report is not None
                and report.status is HealthStatus.HEALTHY
            ):
                self._resolve_alert.execute(
                    existing.id,
                    verified_clear=True,
                )
        return tuple(alerts)

    def critical_mismatch(
        self,
        *,
        reason: str,
        correlation_id: CorrelationId | None = None,
    ) -> Alert:
        return self._raise_alert.execute(
            alert_type=AlertType.CRITICAL_MISMATCH,
            severity=AlertSeverity.CRITICAL,
            title="Critical reconciliation mismatch",
            reason=reason,
            deduplication_key="reconciliation:critical-mismatch",
            correlation_id=correlation_id,
        )

    def trading_readiness_lost(
        self,
        *,
        reason: str,
        correlation_id: CorrelationId | None = None,
    ) -> Alert:
        return self._raise_alert.execute(
            alert_type=AlertType.TRADING_READINESS_LOST,
            severity=AlertSeverity.CRITICAL,
            title="Trading readiness lost",
            reason=reason,
            deduplication_key="runtime:trading-readiness-lost",
            correlation_id=correlation_id,
        )

    def kill_switch_active(
        self,
        *,
        reason: str,
        correlation_id: CorrelationId | None = None,
    ) -> Alert:
        return self._raise_alert.execute(
            alert_type=AlertType.KILL_SWITCH_ACTIVE,
            severity=AlertSeverity.CRITICAL,
            title="Kill switch active",
            reason=reason,
            deduplication_key="safety:kill-switch-active",
            correlation_id=correlation_id,
        )
