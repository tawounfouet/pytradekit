"""Provider-neutral errors raised by broker anti-corruption layers."""

from __future__ import annotations

from pytradekit.shared import PyTradeKitError


class ProviderError(PyTradeKitError):
    """Base error for an external trading provider boundary."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        operation: str,
        status_code: int | None = None,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.status_code = status_code
        self.provider_code = provider_code


class ProviderAuthenticationError(ProviderError):
    """Provider authentication failed."""


class ProviderAuthorizationError(ProviderError):
    """Provider authorization failed."""


class ProviderRateLimitError(ProviderError):
    """Provider rate limit prevented the requested operation."""


class ProviderUnavailableError(ProviderError):
    """Provider or transport is temporarily unavailable for a safe read."""


class ProviderRejectedOperationError(ProviderError):
    """Provider knowingly rejected an economic or protocol operation."""


class ProviderProtocolError(ProviderError):
    """Provider payload or protocol state cannot be mapped safely."""


class ProviderUncertainOutcomeError(ProviderError):
    """Economic command outcome is unknown and requires reconciliation."""


class ProviderStateReconciliationRequired(ProviderError):
    """Provider state requires an explicit snapshot/reconciliation path."""


class ProviderUnsupportedStateError(ProviderError):
    """Provider state belongs to a capability outside the qualified scope."""
