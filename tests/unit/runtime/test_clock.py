"""Unit tests for clock runtime abstractions."""

from datetime import UTC, datetime, timedelta

from pytradekit.runtime import ClockPort, SystemClock


def read_clock(clock: ClockPort) -> datetime:
    """Read any object satisfying the ClockPort protocol."""
    return clock.now()


def test_system_clock_satisfies_clock_port() -> None:
    now = read_clock(SystemClock())

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert now <= datetime.now(UTC)
