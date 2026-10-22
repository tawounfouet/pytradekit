"""Translate Alpaca SDK failures into provider-neutral PyTradeKit errors."""

from __future__ import annotations

from enum import StrEnum

from alpaca.common.exceptions import APIError

from pytradekit.brokers.errors import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRejectedOperationError,
    ProviderUnavailableError,
    ProviderUncertainOutcomeError,
)

from .contract import ALPACA_PROVIDER_KEY


class AlpacaOperation(StrEnum):
    """Operation class used to apply safe error semantics."""

    READ = "read"
    SUBMIT = "submit"
    CANCEL = "cancel"

    @property
    def is_economic_write(self) -> bool:
        """Return whether an unknown transport outcome can create an economic race."""

        return self in {AlpacaOperation.SUBMIT, AlpacaOperation.CANCEL}


def translate_alpaca_error(
    error: Exception,
    *,
    operation: AlpacaOperation,
) -> ProviderError:
    """Translate one caught Alpaca boundary exception without leaking SDK errors."""

    if isinstance(error, APIError):
        return _translate_api_error(error, operation=operation)

    if operation.is_economic_write:
        return ProviderUncertainOutcomeError(
            "Alpaca economic command outcome is unknown and requires reconciliation.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
        )

    return ProviderUnavailableError(
        f"Alpaca read operation failed ({type(error).__name__}).",
        provider=ALPACA_PROVIDER_KEY,
        operation=operation.value,
    )


def _translate_api_error(
    error: APIError,
    *,
    operation: AlpacaOperation,
) -> ProviderError:
    status_code = _status_code(error)
    provider_code = _provider_code(error)
    provider_message = _provider_message(error)

    if status_code == 401:
        return ProviderAuthenticationError(
            "Alpaca authentication failed.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
            status_code=status_code,
            provider_code=provider_code,
        )
    if status_code == 403:
        return ProviderAuthorizationError(
            "Alpaca authorization failed.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
            status_code=status_code,
            provider_code=provider_code,
        )
    if status_code == 429:
        if operation.is_economic_write:
            return ProviderUncertainOutcomeError(
                "Alpaca write was rate-limited with an unknown economic outcome.",
                provider=ALPACA_PROVIDER_KEY,
                operation=operation.value,
                status_code=status_code,
                provider_code=provider_code,
            )
        return ProviderRateLimitError(
            "Alpaca read was rate-limited.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
            status_code=status_code,
            provider_code=provider_code,
        )
    if status_code is not None and status_code >= 500:
        if operation.is_economic_write:
            return ProviderUncertainOutcomeError(
                "Alpaca write failed after a server error with an unknown economic outcome.",
                provider=ALPACA_PROVIDER_KEY,
                operation=operation.value,
                status_code=status_code,
                provider_code=provider_code,
            )
        return ProviderUnavailableError(
            "Alpaca server is unavailable for the requested read.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
            status_code=status_code,
            provider_code=provider_code,
        )
    if status_code is not None and 400 <= status_code < 500:
        if operation.is_economic_write:
            return ProviderRejectedOperationError(
                _safe_rejection_message(provider_message),
                provider=ALPACA_PROVIDER_KEY,
                operation=operation.value,
                status_code=status_code,
                provider_code=provider_code,
            )
        return ProviderProtocolError(
            "Alpaca rejected the provider read request.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
            status_code=status_code,
            provider_code=provider_code,
        )

    if operation.is_economic_write:
        return ProviderUncertainOutcomeError(
            "Alpaca write outcome is unknown and requires reconciliation.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation.value,
            status_code=status_code,
            provider_code=provider_code,
        )
    return ProviderProtocolError(
        "Alpaca returned an unclassified API error.",
        provider=ALPACA_PROVIDER_KEY,
        operation=operation.value,
        status_code=status_code,
        provider_code=provider_code,
    )


def _status_code(error: APIError) -> int | None:
    try:
        value: object = error.status_code
    except Exception:
        return None
    return value if isinstance(value, int) else None


def _provider_code(error: APIError) -> str | None:
    try:
        value: object = error.code
    except Exception:
        return None
    if value is None:
        return None
    return str(value)


def _provider_message(error: APIError) -> str | None:
    try:
        value: object = error.message
    except Exception:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _safe_rejection_message(provider_message: str | None) -> str:
    if provider_message is None:
        return "Alpaca rejected the economic command."
    return f"Alpaca rejected the economic command: {provider_message}"
