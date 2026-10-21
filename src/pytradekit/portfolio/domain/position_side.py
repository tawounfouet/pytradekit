"""Derived position side."""

from enum import StrEnum


class PositionSide(StrEnum):
    """Canonical side derived from signed position quantity."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"
