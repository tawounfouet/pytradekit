"""Operational readiness aggregation over authoritative runtime evidence."""

from datetime import datetime

from pytradekit.operations.domain import (
    HealthComponent,
    HealthStatus,
    LivenessStatus,
    OperationalReadinessReport,
)
from pytradekit.operations.services.health_registry import HealthRegistry
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.runtime.trading_readiness import TradingReadinessReport
from pytradekit.shared import require_utc_datetime

_DEFAULT_CRITICAL_COMPONENTS = frozenset(
    {
        HealthComponent.DATABASE,
        HealthComponent.BROKER_COMMAND,
        HealthComponent.RUNTIME,
    }
)


class LivenessService:
    """Compute process liveness without depending on external dependency health."""

    def evaluate(self, lifecycle: RuntimeLifecycleState) -> LivenessStatus:
        if lifecycle is RuntimeLifecycleState.STOPPED:
            return LivenessStatus.NOT_LIVE
        return LivenessStatus.PROCESS_LIVE


class OperationalReadinessService:
    """Aggregate operational evidence while preserving trading readiness authority."""

    def __init__(
        self,
        *,
        critical_components: frozenset[HealthComponent] = _DEFAULT_CRITICAL_COMPONENTS,
        liveness: LivenessService | None = None,
    ) -> None:
        self._critical_components = critical_components
        self._liveness = liveness or LivenessService()

    def evaluate(
        self,
        *,
        lifecycle: RuntimeLifecycleState,
        health: HealthRegistry,
        trading: TradingReadinessReport,
        observed_at: datetime,
    ) -> OperationalReadinessReport:
        """Return layered process, operational, and trading readiness."""
        now = require_utc_datetime(
            observed_at,
            field_name="Operational readiness evaluation time",
        )
        live = self._liveness.evaluate(lifecycle)
        reasons: list[str] = []

        if live is not LivenessStatus.PROCESS_LIVE:
            reasons.append("PROCESS_NOT_LIVE")

        if lifecycle in {
            RuntimeLifecycleState.STARTING,
            RuntimeLifecycleState.DRAINING,
            RuntimeLifecycleState.STOPPED,
        }:
            reasons.append(f"RUNTIME_{lifecycle.value}")

        for component in sorted(
            self._critical_components,
            key=lambda item: item.value,
        ):
            report = health.get(component, at=now)
            if report is None:
                reasons.append(f"MISSING_HEALTH_{component.value}")
                continue
            if report.status is not HealthStatus.HEALTHY:
                reasons.append(
                    f"{component.value}_{report.status.value}"
                )

        operational_ready = (
            live is LivenessStatus.PROCESS_LIVE
            and lifecycle in {
                RuntimeLifecycleState.READY,
                RuntimeLifecycleState.DEGRADED,
            }
            and not reasons
        )

        return OperationalReadinessReport(
            liveness=live,
            operational_ready=operational_ready,
            trading_ready=trading.trading_ready,
            reasons=tuple(reasons),
            observed_at=now,
        )
