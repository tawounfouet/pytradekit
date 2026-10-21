"""Common domain error hierarchy for PyTradeKit."""


class PyTradeKitError(Exception):
    """Base exception for errors raised by PyTradeKit."""


class DomainValidationError(PyTradeKitError):
    """Raised when a domain value cannot satisfy its construction rules."""


class InvariantViolationError(PyTradeKitError):
    """Raised when an established domain invariant would be violated."""
