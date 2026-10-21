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
from pytradekit.shared.ids import EventId, InstrumentId

__all__ = [
    "CausationId",
    "CorrelationId",
    "Currency",
    "DomainValidationError",
    "EventId",
    "InstrumentId",
    "InvariantViolationError",
    "PyTradeKitError",
]
