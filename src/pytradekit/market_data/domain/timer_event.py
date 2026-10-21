"""Deterministic strategy timer event."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class TimerEvent:
    """Runtime-generated scheduled event independent from wall clock time."""

    name: str
    event_time: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainValidationError("TimerEvent name must be a non-empty string.")
        require_utc_datetime(self.event_time, field_name="TimerEvent event_time")
