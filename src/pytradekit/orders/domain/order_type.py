"""Order type definitions."""

from enum import StrEnum


class OrderType(StrEnum):
    """Order types supported by milestone 0.2."""

    MARKET = "market"
    LIMIT = "limit"
