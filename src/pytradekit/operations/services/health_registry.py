"""Freshness-aware component health registry."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

from pytradekit.operations.domain import (
    HealthComponent,
    HealthReport,
    HealthSnapshot,
    HealthStatus,
)
from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class HealthFreshnessPolicy:
    """Freshness TTLs for component observations."""

    default_ttl: timedelta = timedelta(seconds=30)
    overrides: dict[HealthComponent, timedelta] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_ttl <= timedelta(0):
            raise DomainValidationError("Health default TTL must be positive.")
        for component, ttl in self.overrides.items():
            if not isinstance(component, HealthComponent):
                raise DomainValidationError("Health freshness component is invalid.")
            if ttl <= timedelta(0):
                raise DomainValidationError("Health freshness TTL must be positive.")

    def ttl_for(self, component: HealthComponent) -> timedelta:
        return self.overrides.get(component, self.default_ttl)


class HealthRegistry:
    """Store latest evidence and expire stale observations deterministically."""

    def __init__(
        self,
        *,
        freshness: HealthFreshnessPolicy | None = None,
    ) -> None:
        self._freshness = freshness or HealthFreshnessPolicy()
        self._reports: dict[HealthComponent, HealthReport] = {}
        self._lock = Lock()

    def update(self, report: HealthReport) -> None:
        """Register newer health evidence for one component."""
        with self._lock:
            current = self._reports.get(report.component)
            if current is not None and report.observed_at < current.observed_at:
                raise DomainValidationError(
                    "HealthRegistry cannot replace newer evidence with older evidence."
                )
            self._reports[report.component] = report

    def get(
        self,
        component: HealthComponent,
        *,
        at: datetime,
    ) -> HealthReport | None:
        """Return fresh evidence or an UNKNOWN stale replacement."""
        now = require_utc_datetime(at, field_name="HealthRegistry evaluation time")
        with self._lock:
            report = self._reports.get(component)
        if report is None:
            return None
        if now - report.observed_at >= self._freshness.ttl_for(component):
            return report.as_stale(observed_at=now)
        return report

    def snapshot(self, *, at: datetime) -> HealthSnapshot:
        """Return all known reports after freshness evaluation."""
        now = require_utc_datetime(at, field_name="HealthRegistry snapshot time")
        with self._lock:
            components = tuple(sorted(self._reports, key=lambda item: item.value))
        reports = tuple(
            report
            for component in components
            if (report := self.get(component, at=now)) is not None
        )
        return HealthSnapshot(reports=reports, observed_at=now)

    def critical_healthy(
        self,
        *,
        components: frozenset[HealthComponent],
        at: datetime,
    ) -> bool:
        """Return true only when every required critical component is HEALTHY."""
        for component in components:
            report = self.get(component, at=at)
            if report is None or report.status is not HealthStatus.HEALTHY:
                return False
        return True
