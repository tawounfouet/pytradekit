"""Safety governance errors."""

from pytradekit.shared import PyTradeKitError


class SafetyGovernanceError(PyTradeKitError):
    """Base safety governance failure."""


class SafetyConcurrencyError(SafetyGovernanceError):
    """Raised when optimistic governance state is stale."""


class DangerousActionConfirmationError(SafetyGovernanceError):
    """Raised when dangerous-action confirmation is missing or invalid."""


class KillSwitchReleaseDeniedError(SafetyGovernanceError):
    """Raised when underlying safety evidence cannot support release."""
