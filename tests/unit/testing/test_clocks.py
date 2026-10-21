"""Unit tests for deterministic testing clocks."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from pytradekit.runtime import ClockPort
from pytradekit.shared import DomainValidationError
from pytradekit.testing import FakeClock


def read_clock(clock: ClockPort) -> datetime:
    """Read any object satisfying the ClockPort protocol."""
    return clock.now()


def test_fake_clock_satisfies_clock_port() -> None:
    initial = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)

    clock = FakeClock.at(initial)

    assert read_clock(clock) == initial


def test_fake_clock_advance_is_deterministic() -> None:
    initial = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
    clock = FakeClock.at(initial)

    result = clock.advance(timedelta(minutes=30))

    assert result == datetime(2026, 10, 21, 20, 30, tzinfo=UTC)
    assert clock.now() == result


def test_fake_clock_set_replaces_current_time() -> None:
    initial = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
    target = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)
    clock = FakeClock.at(initial)

    result = clock.set(target)

    assert result == target
    assert clock.now() == target


def test_fake_clock_rejects_naive_initial_time() -> None:
    with pytest.raises(DomainValidationError, match="timezone-aware"):
        FakeClock.at(datetime(2026, 10, 21, 20, 0))


def test_fake_clock_rejects_naive_set_time() -> None:
    clock = FakeClock.at(datetime(2026, 10, 21, 20, 0, tzinfo=UTC))

    with pytest.raises(DomainValidationError, match="timezone-aware"):
        clock.set(datetime(2026, 10, 21, 21, 0))


def test_fake_clock_rejects_non_timedelta_advance() -> None:
    clock = FakeClock.at(datetime(2026, 10, 21, 20, 0, tzinfo=UTC))
    invalid_delta = cast(timedelta, 30)

    with pytest.raises(DomainValidationError, match="timedelta"):
        clock.advance(invalid_delta)
