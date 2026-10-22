"""Unit tests for PAPER runtime configuration primitives."""

import pytest

from pytradekit.runtime import RuntimeEnvironment, RuntimeProfile, SecretRef
from pytradekit.runtime.errors import RuntimeConfigurationError


def _environment() -> dict[str, str]:
    return {
        "PYTRADEKIT_RUNTIME_ENVIRONMENT": "PAPER",
        "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID": "account-12345678",
    }


def test_alpaca_paper_profile_loads_only_safe_configuration() -> None:
    profile = RuntimeProfile.alpaca_paper_from_environment(_environment())

    assert profile.provider == "alpaca"
    assert profile.environment is RuntimeEnvironment.PAPER
    assert profile.market_data_feed == "iex"
    assert profile.api_key_ref == SecretRef("env://PYTRADEKIT_ALPACA_PAPER_API_KEY")
    assert profile.api_secret_ref == SecretRef("env://PYTRADEKIT_ALPACA_PAPER_SECRET_KEY")
    assert profile.database_url_ref == SecretRef("env://PYTRADEKIT_DATABASE_URL")


def test_runtime_profile_rejects_live_environment() -> None:
    environ = _environment()
    environ["PYTRADEKIT_RUNTIME_ENVIRONMENT"] = "LIVE"

    with pytest.raises(RuntimeConfigurationError, match="must be PAPER"):
        RuntimeProfile.alpaca_paper_from_environment(environ)


def test_runtime_profile_requires_explicit_environment() -> None:
    environ = _environment()
    environ.pop("PYTRADEKIT_RUNTIME_ENVIRONMENT")

    with pytest.raises(RuntimeConfigurationError, match="PYTRADEKIT_RUNTIME_ENVIRONMENT"):
        RuntimeProfile.alpaca_paper_from_environment(environ)


def test_runtime_profile_requires_expected_account() -> None:
    environ = _environment()
    environ["PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID"] = ""

    with pytest.raises(RuntimeConfigurationError, match="EXPECTED_ACCOUNT_ID"):
        RuntimeProfile.alpaca_paper_from_environment(environ)


def test_runtime_profile_is_hard_locked_to_iex() -> None:
    environ = _environment()
    environ["PYTRADEKIT_ALPACA_DATA_FEED"] = "sip"

    with pytest.raises(RuntimeConfigurationError, match="hard-locked to 'iex'"):
        RuntimeProfile.alpaca_paper_from_environment(environ)


def test_profile_repr_masks_account_and_contains_only_secret_references() -> None:
    profile = RuntimeProfile.alpaca_paper_from_environment(_environment())

    rendered = repr(profile)

    assert "account-12345678" not in rendered
    assert "5678" in rendered
    assert "env://PYTRADEKIT_ALPACA_PAPER_API_KEY" in rendered
    assert "env://PYTRADEKIT_ALPACA_PAPER_SECRET_KEY" in rendered
