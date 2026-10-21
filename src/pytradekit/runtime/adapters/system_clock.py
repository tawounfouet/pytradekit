"""System-backed clock adapter."""

from datetime import UTC, datetime


class SystemClock:
    """Clock adapter backed by the host system time."""

    def now(self) -> datetime:
        """Return the current system time in UTC."""
        return datetime.now(UTC)
