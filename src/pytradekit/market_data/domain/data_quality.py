"""Historical data quality classifications."""

from dataclasses import dataclass
from enum import StrEnum


class DataQuality(StrEnum):
    """Canonical historical data quality findings."""

    OK = "ok"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"
    STALE = "stale"
    INVALID = "invalid"
    GAP = "gap"


@dataclass(frozen=True, slots=True)
class DataQualityFinding:
    """One deterministic validation finding."""

    quality: DataQuality
    message: str
