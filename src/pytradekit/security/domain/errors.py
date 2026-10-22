"""Security errors."""

from pytradekit.shared import PyTradeKitError


class SecurityError(PyTradeKitError):
    """Base error for security behavior."""


class AuthorizationDeniedError(SecurityError):
    """Raised when an authorization decision denies an action."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(f"Authorization denied: {reason_code}.")
