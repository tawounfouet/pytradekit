"""Canonical level-1 quote observation."""

from __future__ import annotations

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
class Quote:
    """Provider-neutral bid/ask market observation for one instrument."""

    instrument_id: InstrumentId
    bid_price: Price | None
    bid_size: Quantity
    ask_price: Price | None
    ask_size: Quantity
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("Quote instrument_id must be an InstrumentId.")
        if self.bid_price is not None and not isinstance(self.bid_price, Price):
            raise DomainValidationError("Quote bid_price must be Price or None.")
        if self.ask_price is not None and not isinstance(self.ask_price, Price):
            raise DomainValidationError("Quote ask_price must be Price or None.")
        if not isinstance(self.bid_size, Quantity):
            raise DomainValidationError("Quote bid_size must be a Quantity.")
        if not isinstance(self.ask_size, Quantity):
            raise DomainValidationError("Quote ask_size must be a Quantity.")
        if self.bid_price is None and self.ask_price is None:
            raise DomainValidationError("Quote requires at least one priced side.")
        if (
            self.bid_price is not None
            and self.ask_price is not None
            and self.bid_price.currency != self.ask_price.currency
        ):
            raise DomainValidationError("Quote bid and ask currencies must match.")
        require_utc_datetime(self.occurred_at, field_name="Quote occurred_at")
