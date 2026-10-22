"""Security errors."""

from pytradekit.shared import PyTradeKitError


class SecurityError(PyTradeKitError):
    """Base error for security behavior."""


class AuthorizationDeniedError(SecurityError):
    """Raised when an authorization decision denies an action."""
