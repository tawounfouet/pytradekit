"""Operational health evidence without trading state mutation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from pytradekit.shared import DomainValidationError, require_utc_datetime


class HealthStatus(StrEnum):
    """P0 component health status."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class HealthComponent(StrEnum):
    """Operational dependencies observed independently."""

    DATABASE = "DATABASE"
    BROKER_READ = "BROKER_READ"
    BROKER_COMMAND = "BROKER_COMMAND"
    BROKER_STREAM = "BROKER_STREAM"
    OUTBOX = "OUTBOX"
    INBOX = "INBOX"
    RECONCILIATION = "RECONCILIATION"
    RUNTIME = "RUNTIME"
    MARKET_DATA = "MARKET_DATA"


_FORBIDDEN_DETAIL_FRAGMENTS = (
    "secret",
    "password",
    "api_key",
    "apikey",
    "token",
    "credential",
)


@dataclass(frozen=True, slots=True)
class HealthReport:
    """One sanitized component health observation."""

    component: HealthComponent
    status: HealthStatus
    observed_at: datetime
    message: str
    last_success_at: datetime | None = None
    details: Mapping[str, str | int | bool | None] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(self.component, HealthComponent):
            raise DomainValidationError("HealthReport component is invalid.")
        if not isinstance(self.status, HealthStatus):
            raise DomainValidationError("HealthReport status is invalid.")
        require_utc_datetime(self.observed_at, field_name="HealthReport observed_at")
        if not isinstance(self.message, str) or not self.message.strip():
            raise DomainValidationError("HealthReport message must be non-empty.")
        if self.last_success_at is not None:
            require_utc_datetime(
                self.last_success_at,
                field_name="HealthReport last_success_at",
            )
            if self.last_success_at > self.observed_at:
                raise DomainValidationError(
                    "HealthReport last_success_at cannot exceed observed_at."
                )
        safe_details = dict(self.details)
        for key in safe_details:
            lowered = key.lower()
            if any(fragment in lowered for fragment in _FORBIDDEN_DETAIL_FRAGMENTS):
                raise DomainValidationError(
                    f"HealthReport detail field {key!r} may expose secrets."
                )
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "details", MappingProxyType(safe_details))

    def as_stale(self, *, observed_at: datetime) -> "HealthReport":
        """Return UNKNOWN evidence when the previous observation has expired."""
        now = require_utc_datetime(
            observed_at,
            field_name="HealthReport stale evaluation time",
        )
        return HealthReport(
            component=self.component,
            status=HealthStatus.UNKNOWN,
            observed_at=now,
            message=f"{self.component.value} health evidence is stale.",
            last_success_at=self.last_success_at,
            details={"stale": True},
        )


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    """Sanitized aggregate snapshot of component evidence."""

    reports: tuple[HealthReport, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        require_utc_datetime(
            self.observed_at,
            field_name="HealthSnapshot observed_at",
        )

    @property
    def aggregate_status(self) -> HealthStatus:
        """Aggregate without hiding unhealthy or unknown evidence."""
        statuses = {report.status for report in self.reports}
        if not statuses:
            return HealthStatus.UNKNOWN
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get(self, component: HealthComponent) -> HealthReport | None:
        """Return one component report from the detached snapshot."""
        return next(
            (report for report in self.reports if report.component is component),
            None,
        )
