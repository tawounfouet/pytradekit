"""Deterministic clocks for tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self

from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(slots=True)
class FakeClock:
    """Mutable deterministic clock controlled explicitly by tests."""

    _current: datetime

    def __post_init__(self) -> None:
        """Validate the initial time."""
        require_utc_datetime(self._current, field_name="FakeClock current time")

    @classmethod
    def at(cls, initial_time: datetime) -> Self:
        """Create a deterministic clock at a specific UTC time."""
        require_utc_datetime(initial_time, field_name="FakeClock initial time")
        return cls(initial_time)

    def now(self) -> datetime:
        """Return the currently configured deterministic time."""
        return self._current

    def advance(self, delta: timedelta) -> datetime:
        """Advance the clock by a deterministic duration and return the new time."""
        raw_delta: object = delta

        if not isinstance(raw_delta, timedelta):
            raise DomainValidationError("FakeClock delta must be a timedelta.")

        self._current = require_utc_datetime(
            self._current + raw_delta,
            field_name="FakeClock current time",
        )
        return self._current

    def set(self, new_time: datetime) -> datetime:
        """Set the clock to a specific UTC time and return it."""
        self._current = require_utc_datetime(
            new_time,
            field_name="FakeClock new time",
        )
        return self._current
