"""Order side definitions."""

from enum import StrEnum


class OrderSide(StrEnum):
    """Canonical order direction."""

    BUY = "buy"
    SELL = "sell"
