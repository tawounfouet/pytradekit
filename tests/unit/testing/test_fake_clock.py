"""Unit tests for FakeClock."""

from datetime import UTC, datetime, timedelta

import pytest

from pytradekit.shared import DomainValidationError
from pytradekit.testing import FakeClock


def test_fake_clock_returns_initial_time() -> None:
    initial = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    clock = FakeClock.at(initial)

    assert clock.now() == initial


def test_fake_clock_advance_is_deterministic() -> None:
    initial = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    clock = FakeClock.at(initial)

    advanced = clock.advance(timedelta(minutes=5))

    assert advanced == datetime(2026, 10, 21, 12, 5, tzinfo=UTC)
    assert clock.now() == advanced


def test_fake_clock_set_replaces_current_time() -> None:
    clock = FakeClock.at(datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    target = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)

    result = clock.set(target)

    assert result == target
    assert clock.now() == target


def test_fake_clock_rejects_naive_initial_time() -> None:
    with pytest.raises(DomainValidationError, match="timezone-aware"):
        FakeClock.at(datetime(2026, 10, 21, 12, 0))


def test_fake_clock_rejects_naive_set_time() -> None:
    clock = FakeClock.at(datetime(2026, 10, 21, 12, 0, tzinfo=UTC))

    with pytest.raises(DomainValidationError, match="timezone-aware"):
        clock.set(datetime(2026, 10, 21, 13, 0))


def test_fake_clock_can_advance_backwards_explicitly() -> None:
    initial = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    clock = FakeClock.at(initial)

    clock.advance(timedelta(hours=-1))

    assert clock.now() == datetime(2026, 10, 21, 11, 0, tzinfo=UTC)
