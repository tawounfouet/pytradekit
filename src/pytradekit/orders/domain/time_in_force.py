"""Time-in-force definitions."""

from enum import StrEnum


class TimeInForce(StrEnum):
    """Canonical time-in-force values supported by milestone 0.2."""

    DAY = "day"
    GTC = "gtc"
