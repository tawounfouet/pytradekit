"""LOT-07 secret-provider and runtime security qualification."""

from pathlib import Path

import pytest

from pytradekit.runtime import (
    ExternalSecretsProvider,
    FileSecrets,
    RoutedSecrets,
    RuntimeProfile,
    RuntimeSecurityConfig,
    SecretRef,
)
from pytradekit.runtime.adapters import EnvironmentSecrets
from pytradekit.runtime.errors import RuntimeConfigurationError, SecretResolutionError


def _environment() -> dict[str, str]:
    return {
        "PYTRADEKIT_RUNTIME_ENVIRONMENT": "PAPER",
        "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID": "account-12345678",
    }


def test_profile_accepts_secret_references_without_secret_values() -> None:
    environ = _environment()
    environ["PYTRADEKIT_ALPACA_API_KEY_REF"] = "external://alpaca/api-key"
    environ["PYTRADEKIT_ALPACA_SECRET_KEY_REF"] = "file:///run/secrets/alpaca_secret"
    environ["PYTRADEKIT_DATABASE_URL_REF"] = "external://postgres/url"

    profile = RuntimeProfile.alpaca_paper_from_environment(environ)

    assert profile.api_key_ref == SecretRef("external://alpaca/api-key")
    assert profile.api_secret_ref == SecretRef("file:///run/secrets/alpaca_secret")
    assert profile.database_url_ref == SecretRef("external://postgres/url")


def test_file_secrets_are_confined_to_configured_root(tmp_path: Path) -> None:
    root = tmp_path / "secrets"
    root.mkdir()
    secret = root / "api-key"
    secret.write_text("credential-value\n", encoding="utf-8")
    provider = FileSecrets(root)

    assert provider.resolve(SecretRef("file://api-key")) == "credential-value"

    with pytest.raises(SecretResolutionError, match="escapes"):
        provider.resolve(SecretRef("file://../outside"))


def test_external_provider_failure_is_sanitized() -> None:
    def failing_lookup(locator: str) -> str:
        _ = locator
        raise RuntimeError("provider detail contains sensitive backend context")

    provider = ExternalSecretsProvider(failing_lookup)

    with pytest.raises(SecretResolutionError) as captured:
        provider.resolve(SecretRef("external://alpaca/api-key"))

    assert "sensitive backend context" not in str(captured.value)
    assert "external://alpaca/api-key" in str(captured.value)


def test_routed_secrets_dispatches_by_reference_scheme(tmp_path: Path) -> None:
    root = tmp_path / "secrets"
    root.mkdir()
    (root / "database-url").write_text("postgresql://value", encoding="utf-8")
    secrets = RoutedSecrets(
        {
            "env": EnvironmentSecrets({"API_KEY": "env-value"}),
            "file": FileSecrets(root),
            "external": ExternalSecretsProvider(
                lambda locator: "external-value" if locator == "broker/key" else None
            ),
        }
    )

    assert secrets.resolve(SecretRef("env://API_KEY")) == "env-value"
    assert (
        secrets.resolve(SecretRef("file://database-url"))
        == "postgresql://value"
    )
    assert secrets.resolve(SecretRef("external://broker/key")) == "external-value"


def test_production_security_requires_database_tls() -> None:
    production = RuntimeSecurityConfig.production_like()
    local = RuntimeSecurityConfig.local_development()

    assert production.database_require_tls is True
    assert local.database_require_tls is False


def test_runtime_profile_rejects_unapproved_broker_endpoint() -> None:
    environ = _environment()
    environ["PYTRADEKIT_ALPACA_TRADING_ENDPOINT"] = "https://api.alpaca.markets"

    with pytest.raises(RuntimeConfigurationError, match="approved PAPER"):
        RuntimeProfile.alpaca_paper_from_environment(environ)
