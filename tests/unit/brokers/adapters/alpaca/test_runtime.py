"""Unit tests for Alpaca PAPER runtime composition and readiness."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from pytradekit.brokers.adapters.alpaca.runtime import (
    AlpacaPaperStartupReadiness,
    build_alpaca_paper_manifest,
    build_alpaca_paper_runtime,
)
from pytradekit.runtime import (
    EnvironmentSecrets,
    ReadinessCheckStatus,
    RuntimeProfile,
)


def _profile() -> RuntimeProfile:
    return RuntimeProfile.alpaca_paper_from_environment(
        {
            "PYTRADEKIT_RUNTIME_ENVIRONMENT": "PAPER",
            "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID": "paper-account-1234",
        }
    )


class _FakeReadClient:
    def __init__(
        self,
        *,
        account_id: str = "paper-account-1234",
        account_blocked: bool = False,
        trading_blocked: bool = False,
    ) -> None:
        self._account = SimpleNamespace(
            id=account_id,
            account_blocked=account_blocked,
            trading_blocked=trading_blocked,
        )

    def get_account(self) -> object:
        return self._account

    def get_clock(self) -> object:
        return SimpleNamespace(timestamp=datetime.now(UTC), is_open=True)


def test_alpaca_paper_manifest_matches_contract_freeze() -> None:
    manifest = build_alpaca_paper_manifest(_profile())

    assert manifest.provider == "alpaca"
    assert manifest.environment.value == "PAPER"
    assert manifest.sdk_name == "alpaca-py"
    assert manifest.sdk_version == "0.44.0"
    assert manifest.asset_scope == ("US_EQUITY",)
    assert manifest.order_types == ("MARKET", "LIMIT")
    assert manifest.time_in_force == ("DAY",)
    assert manifest.market_data_feed == "iex"


def test_startup_readiness_passes_bootstrap_checks_without_claiming_trading_ready() -> None:
    profile = _profile()
    readiness = AlpacaPaperStartupReadiness(
        profile=profile,
        manifest=build_alpaca_paper_manifest(profile),
        read_client=_FakeReadClient(),
        database_probe=lambda: True,
    )

    report = readiness.run()

    assert report.ready_for_startup is True
    assert all(check.status is ReadinessCheckStatus.PASS for check in report.checks)
    assert report.to_dict()["trading_ready"] is False


def test_startup_readiness_fails_on_wrong_account_without_leaking_full_identity() -> None:
    profile = _profile()
    readiness = AlpacaPaperStartupReadiness(
        profile=profile,
        manifest=build_alpaca_paper_manifest(profile),
        read_client=_FakeReadClient(account_id="different-account"),
        database_probe=lambda: True,
    )

    report = readiness.run()
    account_check = next(check for check in report.checks if check.name == "provider_account")

    assert report.ready_for_startup is False
    assert account_check.status is ReadinessCheckStatus.FAIL
    assert "different-account" not in account_check.detail
    assert profile.expected_account_id not in account_check.detail


def test_startup_readiness_fails_when_account_is_trading_blocked() -> None:
    profile = _profile()
    readiness = AlpacaPaperStartupReadiness(
        profile=profile,
        manifest=build_alpaca_paper_manifest(profile),
        read_client=_FakeReadClient(trading_blocked=True),
        database_probe=lambda: True,
    )

    report = readiness.run()
    state_check = next(check for check in report.checks if check.name == "account_state")

    assert report.ready_for_startup is False
    assert state_check.status is ReadinessCheckStatus.FAIL


def test_startup_readiness_fails_when_database_is_unhealthy() -> None:
    profile = _profile()
    readiness = AlpacaPaperStartupReadiness(
        profile=profile,
        manifest=build_alpaca_paper_manifest(profile),
        read_client=_FakeReadClient(),
        database_probe=lambda: False,
    )

    report = readiness.run()

    assert report.ready_for_startup is False


def test_composition_root_builds_paper_clients_without_network_calls() -> None:
    profile = _profile()
    secrets = EnvironmentSecrets(
        {
            "PYTRADEKIT_ALPACA_PAPER_API_KEY": "paper-key",
            "PYTRADEKIT_ALPACA_PAPER_SECRET_KEY": "paper-secret",
            "PYTRADEKIT_DATABASE_URL": (
                "postgresql+psycopg://pytradekit:pytradekit@localhost/pytradekit"
            ),
        }
    )

    composition = build_alpaca_paper_runtime(profile, secrets)

    assert composition.profile.environment.value == "PAPER"
    assert composition.manifest.provider == "alpaca"
    assert composition.command_client._retry == 0
    assert "paper-secret" not in repr(composition)
    composition.engine.dispose()
