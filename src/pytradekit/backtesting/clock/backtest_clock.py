"""Deterministic backtest clock."""

from datetime import datetime

from pytradekit.shared import InvariantViolationError, require_utc_datetime


class BacktestClock:
    """ClockPort implementation advanced only by the backtest runtime."""

    def __init__(self, current_time: datetime) -> None:
        self._current_time = require_utc_datetime(
            current_time,
            field_name="BacktestClock current_time",
        )

    def now(self) -> datetime:
        return self._current_time

    def advance_to(self, timestamp: datetime) -> None:
        value = require_utc_datetime(timestamp, field_name="BacktestClock timestamp")
        if value < self._current_time:
            raise InvariantViolationError("BacktestClock cannot move backwards.")
        self._current_time = value
