"""Order domain and repository errors."""

from pytradekit.shared import DomainValidationError, InvariantViolationError, PyTradeKitError


class InvalidOrderError(DomainValidationError):
    """Raised when an order cannot satisfy construction rules."""


class InvalidOrderTransitionError(InvariantViolationError):
    """Raised when an order lifecycle transition is forbidden."""


class OrderNotCancellableError(InvalidOrderTransitionError):
    """Raised when cancellation is requested from a non-cancellable state."""


class OrderNotFoundError(PyTradeKitError):
    """Raised when an order repository cannot find an order."""


class OrderAlreadyExistsError(PyTradeKitError):
    """Raised when adding an order that already exists."""
