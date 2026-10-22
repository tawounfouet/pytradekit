"""Health monitoring and readiness application operations."""

from datetime import datetime

from pytradekit.operations.domain import (
    HealthSnapshot,
    LivenessStatus,
    OperationalReadinessReport,
)
from pytradekit.operations.ports import HealthCheckPort
from pytradekit.operations.services import (
    HealthRegistry,
    LivenessService,
    OperationalReadinessService,
)
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.runtime.operations import (
    RuntimeAdmissionGate,
    RuntimeLifecycleState,
)
from pytradekit.runtime.trading_readiness import TradingReadinessReport


class HealthMonitor:
    """Run read-only dependency checks and update the registry."""

    def __init__(
        self,
        *,
        registry: HealthRegistry,
        checks: tuple[HealthCheckPort, ...],
        observer: RuntimeObserver | None = None,
    ) -> None:
        if not checks:
            raise ValueError("HealthMonitor requires at least one health check.")
        self._registry = registry
        self._checks = checks
        self._observer = observer

    def run(self) -> HealthSnapshot:
        reports = tuple(check.check() for check in self._checks)
        status_value = {
            "UNHEALTHY": 0,
            "UNKNOWN": 1,
            "DEGRADED": 2,
            "HEALTHY": 3,
        }
        for report in reports:
            self._registry.update(report)
            if self._observer is not None:
                self._observer.set_labeled_gauge(
                    "health_component_status",
                    labels={"component": report.component.value},
                    value=status_value[report.status.value],
                )
                if report.status.value == "UNHEALTHY":
                    self._observer.increment_labeled(
                        "health_check_failures_total",
                        labels={"component": report.component.value},
                    )
        observed_at = max(report.observed_at for report in reports)
        return self._registry.snapshot(at=observed_at)


class GetHealthReport:
    """Return one freshness-aware operational snapshot."""

    def __init__(self, registry: HealthRegistry) -> None:
        self._registry = registry

    def execute(self, *, at: datetime) -> HealthSnapshot:
        return self._registry.snapshot(at=at)


class GetLiveness:
    """Return liveness independently from dependency readiness."""

    def __init__(self, service: LivenessService | None = None) -> None:
        self._service = service or LivenessService()

    def execute(self, lifecycle: RuntimeLifecycleState) -> LivenessStatus:
        return self._service.evaluate(lifecycle)


class GetReadinessReport:
    """Expose operational readiness without recomputing trading truth."""

    def __init__(
        self,
        *,
        health: HealthRegistry,
        service: OperationalReadinessService | None = None,
    ) -> None:
        self._health = health
        self._service = service or OperationalReadinessService()

    def execute(
        self,
        *,
        lifecycle: RuntimeLifecycleState,
        trading: TradingReadinessReport,
        observed_at: datetime,
    ) -> OperationalReadinessReport:
        return self._service.evaluate(
            lifecycle=lifecycle,
            health=self._health,
            trading=trading,
            observed_at=observed_at,
        )


class ApplyOperationalReadiness:
    """Reflect readiness into the existing runtime admission gate."""

    def __init__(
        self,
        gate: RuntimeAdmissionGate,
        *,
        observer: RuntimeObserver | None = None,
    ) -> None:
        self._gate = gate
        self._observer = observer
        self._last_state: tuple[bool, bool] | None = None

    def execute(self, report: OperationalReadinessReport) -> None:
        state = (report.operational_ready, report.trading_ready)
        if self._observer is not None:
            self._observer.set_gauge(
                "operational_ready",
                1 if report.operational_ready else 0,
            )
            self._observer.set_gauge(
                "trading_ready",
                1 if report.trading_ready else 0,
            )
            if state != self._last_state:
                self._observer.increment_labeled(
                    "readiness_transitions_total",
                    labels={
                        "status": (
                            "READY"
                            if report.operational_ready and report.trading_ready
                            else "NOT_READY"
                        )
                    },
                )
                self._observer.event(
                    "OperationalReadinessChanged",
                    operational_ready=report.operational_ready,
                    trading_ready=report.trading_ready,
                )
        self._last_state = state
        if report.operational_ready and report.trading_ready:
            self._gate.mark_ready()
        else:
            self._gate.mark_degraded()
