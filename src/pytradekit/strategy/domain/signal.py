"""Canonical strategy signal."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pytradekit.shared import DomainValidationError, InstrumentId, require_utc_datetime


class SignalDirection(StrEnum):
    """Directional market view expressed by a strategy."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass(frozen=True, slots=True)
class Signal:
    """A strategy view that is not yet a trading command."""

    instrument_id: InstrumentId
    direction: SignalDirection
    generated_at: datetime
    strength: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("Signal instrument_id must be an InstrumentId.")
        if not isinstance(self.direction, SignalDirection):
            raise DomainValidationError("Signal direction must be a SignalDirection.")
        require_utc_datetime(self.generated_at, field_name="Signal generated_at")
        if self.strength is not None:
            if not isinstance(self.strength, Decimal) or not self.strength.is_finite():
                raise DomainValidationError("Signal strength must be a finite Decimal or None.")
