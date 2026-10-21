"""Unit tests for shared time primitives."""

from datetime import datetime, timedelta, timezone

import pytest

from pytradekit.shared.errors import DomainValidationError
from pytradekit.shared.time import require_utc_datetime


def test_require_utc_datetime_accepts_utc_datetime() -> None:
    value = datetime(2026, 10, 21, 19, 0, tzinfo=timezone.utc)

    assert require_utc_datetime(value) is value


def test_require_utc_datetime_accepts_zero_offset_timezone() -> None:
    value = datetime(
        2026,
        10,
        21,
        19,
        0,
        tzinfo=timezone(timedelta(0)),
    )

    assert require_utc_datetime(value) is value


def test_require_utc_datetime_rejects_naive_datetime() -> None:
    value = datetime(2026, 10, 21, 19, 0)

    with pytest.raises(DomainValidationError, match="timezone-aware"):
        require_utc_datetime(value)


def test_require_utc_datetime_rejects_non_utc_offset() -> None:
    value = datetime(
        2026,
        10,
        21,
        21,
        0,
        tzinfo=timezone(timedelta(hours=2)),
    )

    with pytest.raises(DomainValidationError, match="must use UTC"):
        require_utc_datetime(value)
