"""Unit tests for Alpaca error translation semantics."""

from types import SimpleNamespace

from alpaca.common.exceptions import APIError

from pytradekit.brokers import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderRateLimitError,
    ProviderRejectedOperationError,
    ProviderUnavailableError,
    ProviderUncertainOutcomeError,
)
from pytradekit.brokers.adapters.alpaca.errors import (
    AlpacaOperation,
    translate_alpaca_error,
)


def _api_error(status_code: int, *, code: int = 1000, message: str = "failure") -> APIError:
    raw = f'{{"code":{code},"message":"{message}"}}'
    http_error = SimpleNamespace(response=SimpleNamespace(status_code=status_code))
    return APIError(raw, http_error=http_error)  # type: ignore[no-untyped-call]


def test_authentication_and_authorization_are_distinct() -> None:
    assert isinstance(
        translate_alpaca_error(_api_error(401), operation=AlpacaOperation.READ),
        ProviderAuthenticationError,
    )
    assert isinstance(
        translate_alpaca_error(_api_error(403), operation=AlpacaOperation.READ),
        ProviderAuthorizationError,
    )


def test_read_rate_limit_is_rate_limit_not_uncertainty() -> None:
    mapped = translate_alpaca_error(_api_error(429), operation=AlpacaOperation.READ)

    assert isinstance(mapped, ProviderRateLimitError)


def test_write_rate_limit_is_conservative_uncertain_outcome() -> None:
    mapped = translate_alpaca_error(_api_error(429), operation=AlpacaOperation.SUBMIT)

    assert isinstance(mapped, ProviderUncertainOutcomeError)


def test_server_error_is_unavailable_for_read_but_uncertain_for_submit() -> None:
    read = translate_alpaca_error(_api_error(504), operation=AlpacaOperation.READ)
    write = translate_alpaca_error(_api_error(504), operation=AlpacaOperation.SUBMIT)

    assert isinstance(read, ProviderUnavailableError)
    assert isinstance(write, ProviderUncertainOutcomeError)


def test_known_client_error_on_submit_is_rejected_operation() -> None:
    mapped = translate_alpaca_error(
        _api_error(422, code=42210000, message="invalid order"),
        operation=AlpacaOperation.SUBMIT,
    )

    assert isinstance(mapped, ProviderRejectedOperationError)
    assert mapped.status_code == 422
    assert mapped.provider_code == "42210000"


def test_unknown_transport_exception_is_uncertain_only_for_economic_write() -> None:
    write = translate_alpaca_error(ConnectionError("network"), operation=AlpacaOperation.CANCEL)
    read = translate_alpaca_error(ConnectionError("network"), operation=AlpacaOperation.READ)

    assert isinstance(write, ProviderUncertainOutcomeError)
    assert isinstance(read, ProviderUnavailableError)
