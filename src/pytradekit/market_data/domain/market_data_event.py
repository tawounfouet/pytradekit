"""Canonical market data event envelope."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.market_data.domain.bar import Bar
from pytradekit.shared import DomainValidationError, InstrumentId


@dataclass(frozen=True, slots=True)
class MarketDataEvent:
    """One historical market fact exposed to strategy code."""

    bar: Bar
    source_sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.bar, Bar):
            raise DomainValidationError("MarketDataEvent bar must be a Bar.")
        if type(self.source_sequence) is not int or self.source_sequence < 0:
            raise DomainValidationError("MarketDataEvent source_sequence must be non-negative.")

    @property
    def instrument_id(self) -> InstrumentId:
        return self.bar.instrument_id

    @property
    def event_time(self) -> datetime:
        return self.bar.end_time
