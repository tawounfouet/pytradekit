"""Canonical historical OHLC bar."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import (
    DomainValidationError,
    InstrumentId,
    Price,
    Quantity,
    require_utc_datetime,
)


@dataclass(frozen=True, slots=True)
class Bar:
    """Immutable time-bounded OHLCV observation."""

    instrument_id: InstrumentId
    interval: str
    open: Price
    high: Price
    low: Price
    close: Price
    start_time: datetime
    end_time: datetime
    volume: Quantity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("Bar instrument_id must be an InstrumentId.")
        if not isinstance(self.interval, str) or not self.interval.strip():
            raise DomainValidationError("Bar interval must be a non-empty string.")
        prices = (self.open, self.high, self.low, self.close)
        if not all(isinstance(item, Price) for item in prices):
            raise DomainValidationError("Bar OHLC values must be Price values.")
        if len({item.currency for item in prices}) != 1:
            raise DomainValidationError("Bar OHLC prices must use one currency.")
        if self.high.value < max(self.open.value, self.close.value, self.low.value):
            raise DomainValidationError("Bar high must be greater than or equal to OHLC values.")
        if self.low.value > min(self.open.value, self.close.value, self.high.value):
            raise DomainValidationError("Bar low must be less than or equal to OHLC values.")
        if self.volume is not None and not isinstance(self.volume, Quantity):
            raise DomainValidationError("Bar volume must be Quantity or None.")
        start = require_utc_datetime(self.start_time, field_name="Bar start_time")
        end = require_utc_datetime(self.end_time, field_name="Bar end_time")
        if start >= end:
            raise DomainValidationError("Bar start_time must be before end_time.")
