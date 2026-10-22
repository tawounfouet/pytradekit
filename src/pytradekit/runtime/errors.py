"""Runtime configuration and bootstrap errors."""

from pytradekit.shared import PyTradeKitError


class RuntimeConfigurationError(PyTradeKitError):
    """Raised when a runtime profile cannot satisfy bootstrap invariants."""


class SecretResolutionError(PyTradeKitError):
    """Raised when a secret reference cannot be resolved safely."""
