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
    ) -> None:
        self._registry = registry
        self._checks = checks

    def run(self) -> HealthSnapshot:
        reports = tuple(check.check() for check in self._checks)
        for report in reports:
            self._registry.update(report)
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

    def __init__(self, gate: RuntimeAdmissionGate) -> None:
        self._gate = gate

    def execute(self, report: OperationalReadinessReport) -> None:
        if report.operational_ready and report.trading_ready:
            self._gate.mark_ready()
        else:
            self._gate.mark_degraded()
