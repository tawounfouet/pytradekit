"""Stateful operator alerts distinct from log lines."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from pytradekit.shared import CorrelationId, DomainValidationError, require_utc_datetime
from pytradekit.shared.ids import _UUIDIdentifier

_SECRET_MARKERS = (
    "bearer ",
    "password=",
    "secret=",
    "api_key=",
    "apikey=",
    "token=",
    "credential=",
)


@dataclass(frozen=True, slots=True)
class AlertId(_UUIDIdentifier):
    """Typed identifier for one stateful alert."""


class AlertSeverity(StrEnum):
    """P0 alert severity independent from mismatch severity."""

    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(StrEnum):
    """P0 operational alert taxonomy."""

    BROKER_DISCONNECTED = "BROKER_DISCONNECTED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    CRITICAL_MISMATCH = "CRITICAL_MISMATCH"
    UNKNOWN_ORDER_STATE = "UNKNOWN_ORDER_STATE"
    RISK_HALT = "RISK_HALT"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    OUTBOX_BACKLOG = "OUTBOX_BACKLOG"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    TRADING_READINESS_LOST = "TRADING_READINESS_LOST"
    SECRET_POLICY_VIOLATION = "SECRET_POLICY_VIOLATION"


class AlertState(StrEnum):
    """Lifecycle state for an unresolved or resolved alert."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class Alert:
    """Stateful deduplicated alert with explicit acknowledgement and resolution."""

    id: AlertId
    type: AlertType
    severity: AlertSeverity
    state: AlertState
    title: str
    reason: str
    created_at: datetime
    deduplication_key: str
    correlation_id: CorrelationId | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, AlertId):
            raise DomainValidationError("Alert id is invalid.")
        if not isinstance(self.type, AlertType):
            raise DomainValidationError("Alert type is invalid.")
        if not isinstance(self.severity, AlertSeverity):
            raise DomainValidationError("Alert severity is invalid.")
        if not isinstance(self.state, AlertState):
            raise DomainValidationError("Alert state is invalid.")
        require_utc_datetime(self.created_at, field_name="Alert created_at")
        _validate_text(self.title, field_name="Alert title")
        _validate_text(self.reason, field_name="Alert reason")
        _validate_text(self.deduplication_key, field_name="Alert deduplication_key")
        if len(self.deduplication_key) > 300:
            raise DomainValidationError("Alert deduplication_key is too long.")
        if self.acknowledged_at is not None:
            require_utc_datetime(
                self.acknowledged_at,
                field_name="Alert acknowledged_at",
            )
        if self.resolved_at is not None:
            require_utc_datetime(self.resolved_at, field_name="Alert resolved_at")
        if self.state is AlertState.RESOLVED and self.resolved_at is None:
            raise DomainValidationError("RESOLVED alert requires resolved_at.")
        if self.state is not AlertState.RESOLVED and self.resolved_at is not None:
            raise DomainValidationError(
                "Only RESOLVED alert may contain resolved_at."
            )

    @property
    def unresolved(self) -> bool:
        return self.state is not AlertState.RESOLVED

    def acknowledge(self, *, occurred_at: datetime) -> "Alert":
        now = require_utc_datetime(occurred_at, field_name="Alert acknowledgement time")
        if self.state is AlertState.RESOLVED:
            raise DomainValidationError("Resolved alert cannot be acknowledged.")
        if self.state is AlertState.ACKNOWLEDGED:
            return self
        return replace(
            self,
            state=AlertState.ACKNOWLEDGED,
            acknowledged_at=now,
        )

    def resolve(self, *, occurred_at: datetime) -> "Alert":
        now = require_utc_datetime(occurred_at, field_name="Alert resolution time")
        if self.state is AlertState.RESOLVED:
            return self
        return replace(
            self,
            state=AlertState.RESOLVED,
            resolved_at=now,
        )


def _validate_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be non-empty.")
    lowered = value.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        raise DomainValidationError(f"{field_name} may expose secret material.")
