"""Dependency health checks backed by injected read-only probes."""

from collections.abc import Callable
from datetime import datetime

from pytradekit.operations.domain import (
    HealthComponent,
    HealthReport,
    HealthStatus,
)
from pytradekit.runtime.ports import ClockPort


class CallableHealthCheck:
    """Convert a dependency probe into sanitized health evidence."""

    def __init__(
        self,
        *,
        component: HealthComponent,
        probe: Callable[[], bool],
        clock: ClockPort,
        healthy_message: str = "dependency healthy",
        unhealthy_message: str = "dependency unavailable",
    ) -> None:
        self._component = component
        self._probe = probe
        self._clock = clock
        self._healthy_message = healthy_message
        self._unhealthy_message = unhealthy_message
        self._last_success_at: datetime | None = None

    @property
    def component(self) -> HealthComponent:
        return self._component

    def check(self) -> HealthReport:
        now = self._clock.now()
        try:
            healthy = self._probe()
        except Exception as exc:
            return HealthReport(
                component=self._component,
                status=HealthStatus.UNHEALTHY,
                observed_at=now,
                message=self._unhealthy_message,
                last_success_at=self._last_success_at,
                details={"error_type": type(exc).__name__},
            )
        if healthy:
            self._last_success_at = now
            return HealthReport(
                component=self._component,
                status=HealthStatus.HEALTHY,
                observed_at=now,
                message=self._healthy_message,
                last_success_at=now,
            )
        return HealthReport(
            component=self._component,
            status=HealthStatus.UNHEALTHY,
            observed_at=now,
            message=self._unhealthy_message,
            last_success_at=self._last_success_at,
        )
