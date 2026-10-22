"""LOT-07 deployment preflight qualification."""

from pathlib import Path

from pytradekit.runtime import RuntimeProfile, RuntimeSecurityConfig
from pytradekit.runtime.adapters import FileSecrets, RoutedSecrets
from pytradekit.runtime.deployment import DeploymentPreflight


def _profile(root: Path) -> RuntimeProfile:
    return RuntimeProfile.alpaca_paper_from_environment(
        {
            "PYTRADEKIT_RUNTIME_ENVIRONMENT": "PAPER",
            "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID": "account-12345678",
            "PYTRADEKIT_ALPACA_API_KEY_REF": "file://api_key",
            "PYTRADEKIT_ALPACA_SECRET_KEY_REF": "file://secret_key",
            "PYTRADEKIT_DATABASE_URL_REF": "file://database_url",
        }
    )


def test_missing_secret_fails_preflight_closed_without_value_leak(
    tmp_path: Path,
) -> None:
    root = tmp_path / "secrets"
    root.mkdir()
    (root / "api_key").write_text("sensitive-api-key", encoding="utf-8")
    secrets = RoutedSecrets({"file": FileSecrets(root)})
    report = DeploymentPreflight(
        profile=_profile(root),
        secrets=secrets,
        security=RuntimeSecurityConfig.local_development(),
    ).readiness()

    assert report.ready is False
    assert report.reasons == ("REQUIRED_SECRET_UNAVAILABLE",)
    rendered = str(report.to_dict())
    assert "sensitive-api-key" not in rendered
