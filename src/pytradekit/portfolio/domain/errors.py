"""Portfolio domain errors."""

from pytradekit.shared import InvariantViolationError, PyTradeKitError


class PortfolioError(PyTradeKitError):
    """Base error for Portfolio failures."""


class PortfolioInvariantError(InvariantViolationError, PortfolioError):
    """Raised when a portfolio accounting invariant would be violated."""


class BalanceNotFoundError(PortfolioError):
    """Raised when an expected account balance does not exist."""
