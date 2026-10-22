"""Qualification tests for Alpaca rate-limit and server-fault semantics."""

from types import SimpleNamespace

from alpaca.common.exceptions import APIError

from pytradekit.brokers import (
    ProviderRateLimitError,
    ProviderUnavailableError,
    ProviderUncertainOutcomeError,
)
from pytradekit.brokers.adapters.alpaca.errors import (
    AlpacaOperation,
    translate_alpaca_error,
)


def _api_error(status: int) -> APIError:
    http_error = SimpleNamespace(
        response=SimpleNamespace(status_code=status),
        request=None,
    )
    return APIError(  # type: ignore[no-untyped-call]
        '{"code": 50010000, "message": "synthetic provider fault"}',
        http_error=http_error,
    )


def test_read_429_is_rate_limit_not_economic_uncertainty() -> None:
    translated = translate_alpaca_error(
        _api_error(429),
        operation=AlpacaOperation.READ,
    )

    assert isinstance(translated, ProviderRateLimitError)


def test_submit_429_is_uncertain_and_must_not_be_blindly_retried() -> None:
    translated = translate_alpaca_error(
        _api_error(429),
        operation=AlpacaOperation.SUBMIT,
    )

    assert isinstance(translated, ProviderUncertainOutcomeError)


def test_read_503_is_provider_unavailable() -> None:
    translated = translate_alpaca_error(
        _api_error(503),
        operation=AlpacaOperation.READ,
    )

    assert isinstance(translated, ProviderUnavailableError)


def test_submit_503_is_uncertain() -> None:
    translated = translate_alpaca_error(
        _api_error(503),
        operation=AlpacaOperation.SUBMIT,
    )

    assert isinstance(translated, ProviderUncertainOutcomeError)


def test_transport_loss_after_write_is_uncertain() -> None:
    translated = translate_alpaca_error(
        ConnectionResetError("synthetic reset"),
        operation=AlpacaOperation.CANCEL,
    )

    assert isinstance(translated, ProviderUncertainOutcomeError)