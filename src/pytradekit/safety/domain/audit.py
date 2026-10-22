"""Safety governance audit evidence."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.security.domain import ActorId
from pytradekit.shared import CorrelationId, require_utc_datetime


@dataclass(frozen=True, slots=True)
class SafetyAuditEvent:
    """Sanitized audit event for a governed safety action."""

    event_type: str
    actor_id: ActorId
    action: str
    scope_reference: str
    reason: str
    occurred_at: datetime
    correlation_id: CorrelationId | None = None

    def __post_init__(self) -> None:
        require_utc_datetime(self.occurred_at, field_name="SafetyAuditEvent occurred_at")
