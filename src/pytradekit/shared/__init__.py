"""Minimal shared kernel for PyTradeKit.

Only truly cross-context domain primitives belong here.
"""

from pytradekit.shared.currency import Currency
from pytradekit.shared.errors import (
    DomainValidationError,
    InvariantViolationError,
    PyTradeKitError,
)

__all__ = [
    "Currency",
    "DomainValidationError",
    "InvariantViolationError",
    "PyTradeKitError",
]
