"""Clock port for explicit time dependencies."""

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Port exposing the current timezone-aware UTC datetime."""

    def now(self) -> datetime:
        """Return the current time."""
        ...
