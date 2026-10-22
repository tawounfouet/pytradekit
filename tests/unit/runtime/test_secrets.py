"""Unit tests for runtime secret resolution."""

import pytest

from pytradekit.runtime import EnvironmentSecrets, SecretRef
from pytradekit.runtime.errors import SecretResolutionError


def test_environment_secrets_resolves_env_reference() -> None:
    secrets = EnvironmentSecrets({"API_KEY": "secret-value"})

    assert secrets.resolve(SecretRef("env://API_KEY")) == "secret-value"


def test_environment_secrets_rejects_missing_secret() -> None:
    secrets = EnvironmentSecrets({})

    with pytest.raises(SecretResolutionError, match="env://API_KEY"):
        secrets.resolve(SecretRef("env://API_KEY"))


def test_environment_secrets_rejects_unsupported_scheme() -> None:
    secrets = EnvironmentSecrets({"API_KEY": "secret-value"})

    with pytest.raises(SecretResolutionError, match="cannot resolve scheme"):
        secrets.resolve(SecretRef("vault://API_KEY"))


def test_environment_secrets_repr_never_exposes_values() -> None:
    secrets = EnvironmentSecrets({"API_KEY": "super-secret"})

    rendered = repr(secrets)

    assert "super-secret" not in rendered
    assert rendered == "EnvironmentSecrets(source='environment')"
