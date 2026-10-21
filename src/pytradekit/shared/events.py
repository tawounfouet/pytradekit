"""Base domain event primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared.correlation import CausationId, CorrelationId
from pytradekit.shared.errors import DomainValidationError
from pytradekit.shared.ids import EventId
from pytradekit.shared.time import require_utc_datetime


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable base class for domain events."""

    event_id: EventId
    occurred_at: datetime
    correlation_id: CorrelationId
    causation_id: CausationId | None = None
    event_version: int = 1

    def __post_init__(self) -> None:
        """Validate the canonical domain event envelope."""
        raw_event_id: object = self.event_id
        raw_correlation_id: object = self.correlation_id
        raw_causation_id: object = self.causation_id
        raw_event_version: object = self.event_version

        if not isinstance(raw_event_id, EventId):
            raise DomainValidationError("DomainEvent event_id must be an EventId.")

        require_utc_datetime(self.occurred_at, field_name="DomainEvent occurred_at")

        if not isinstance(raw_correlation_id, CorrelationId):
            raise DomainValidationError(
                "DomainEvent correlation_id must be a CorrelationId."
            )

        if raw_causation_id is not None and not isinstance(raw_causation_id, CausationId):
            raise DomainValidationError(
                "DomainEvent causation_id must be a CausationId or None."
            )

        if type(raw_event_version) is not int or raw_event_version < 1:
            raise DomainValidationError(
                "DomainEvent event_version must be an integer greater than or equal to 1."
            )
