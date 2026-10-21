"""Minimal shared kernel for PyTradeKit.

Only truly cross-context domain primitives belong here.
"""

from pytradekit.shared.correlation import CausationId, CorrelationId
from pytradekit.shared.currency import Currency
from pytradekit.shared.errors import (
    DomainValidationError,
    InvariantViolationError,
    PyTradeKitError,
)
from pytradekit.shared.events import DomainEvent
from pytradekit.shared.ids import EventId, InstrumentId
from pytradekit.shared.money import Money
from pytradekit.shared.percentage import Percentage
from pytradekit.shared.price import Price
from pytradekit.shared.quantity import Quantity
from pytradekit.shared.time import require_utc_datetime

__all__ = [
    "CausationId",
    "CorrelationId",
    "Currency",
    "DomainEvent",
    "DomainValidationError",
    "EventId",
    "InstrumentId",
    "InvariantViolationError",
    "Money",
    "Percentage",
    "Price",
    "PyTradeKitError",
    "Quantity",
    "require_utc_datetime",
]
