"""Runtime configuration and bootstrap errors."""

from pytradekit.shared import PyTradeKitError


class RuntimeConfigurationError(PyTradeKitError):
    """Raised when a runtime profile cannot satisfy bootstrap invariants."""


class SecretResolutionError(PyTradeKitError):
    """Raised when a secret reference cannot be resolved safely."""


class RuntimeStartupTimeoutError(PyTradeKitError):
    """Raised when bounded runtime startup exceeds its configured timeout."""


class RuntimeTelemetryFlushTimeoutError(PyTradeKitError):
    """Raised internally when telemetry flush exceeds its shutdown budget."""
