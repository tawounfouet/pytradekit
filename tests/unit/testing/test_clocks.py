"""Protocol and boundary tests for deterministic clocks."""

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


def test_fake_clock_rejects_non_timedelta_advance() -> None:
    clock = FakeClock.at(datetime(2026, 10, 21, 20, 0, tzinfo=UTC))
    invalid_delta = cast(timedelta, 30)

    with pytest.raises(DomainValidationError, match="timedelta"):
        clock.advance(invalid_delta)
