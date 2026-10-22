"""Bounded telemetry shutdown boundary."""

from typing import Protocol


class TelemetryFlushPort(Protocol):
    """Flush buffered telemetry without owning runtime correctness."""

    def flush(self) -> None:
        """Flush currently buffered telemetry."""

        ...
