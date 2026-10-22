"""Alpaca PAPER runtime composition and startup readiness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.brokers.adapters.alpaca.contract import (
    ALPACA_PROVIDER_KEY,
    ALPACA_SDK_VERSION_TARGET,
)
from pytradekit.brokers.adapters.alpaca.stream import AlpacaPaperTradeStream
from pytradekit.persistence.database import (
    create_database_engine,
    create_session_factory,
    database_is_healthy,
)
from pytradekit.runtime import (
    ProviderManifest,
    ReadinessCheck,
    ReadinessCheckStatus,
    RuntimeEnvironment,
    RuntimeProfile,
    RuntimeSecurityConfig,
    SecretsPort,
    StartupReadinessReport,
)

DatabaseProbe = Callable[[], bool]


class AlpacaReadinessClient(Protocol):
    """Minimal read-side client needed by LOT-05 startup readiness."""

    def get_account(self) -> object:
        """Return the current trading account."""

        ...

    def get_clock(self) -> object:
        """Return the provider market clock."""

        ...


class AlpacaPaperCommandClient(TradingClient):
    """TradingClient hard-locked to PAPER with SDK command retries disabled."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        super().__init__(
            api_key=api_key,
            secret_key=secret_key,
            paper=True,
        )
        self._retry = 0


def build_alpaca_paper_manifest(profile: RuntimeProfile) -> ProviderManifest:
    """Build the frozen Alpaca 0.5 provider manifest."""

    _require_alpaca_paper_profile(profile)
    return ProviderManifest(
        provider=ALPACA_PROVIDER_KEY,
        environment=RuntimeEnvironment.PAPER,
        sdk_name="alpaca-py",
        sdk_version=ALPACA_SDK_VERSION_TARGET,
        asset_scope=("US_EQUITY",),
        order_types=("MARKET", "LIMIT"),
        time_in_force=("DAY",),
        capabilities=(
            "ACCOUNT_QUERY",
            "ASSET_QUERY",
            "CANCEL",
            "LATEST_QUOTE",
            "MARKET_ORDER",
            "LIMIT_ORDER",
            "ORDER_QUERY",
            "POSITION_QUERY",
            "TRADE_UPDATES",
        ),
        market_data_feed=profile.market_data_feed,
    )


class AlpacaPaperStartupReadiness:
    """Evaluate LOT-05 bootstrap prerequisites without claiming trading readiness."""

    def __init__(
        self,
        *,
        profile: RuntimeProfile,
        manifest: ProviderManifest,
        read_client: AlpacaReadinessClient,
        database_probe: DatabaseProbe,
    ) -> None:
        _require_alpaca_paper_profile(profile)
        self._profile = profile
        self._manifest = manifest
        self._read_client = read_client
        self._database_probe = database_probe

    def run(self) -> StartupReadinessReport:
        """Evaluate configuration, database, account identity, account state, and clock."""

        checks: list[ReadinessCheck] = [
            ReadinessCheck(
                name="profile",
                status=ReadinessCheckStatus.PASS,
                detail="Alpaca PAPER profile validated.",
            ),
            ReadinessCheck(
                name="provider_manifest",
                status=ReadinessCheckStatus.PASS,
                detail=(
                    f"{self._manifest.sdk_name}=={self._manifest.sdk_version}; "
                    f"feed={self._manifest.market_data_feed}."
                ),
            ),
        ]

        checks.append(self._database_check())
        account, account_check = self._account_identity_check()
        checks.append(account_check)

        if account is not None:
            checks.append(self._account_state_check(account))
        else:
            checks.append(
                ReadinessCheck(
                    name="account_state",
                    status=ReadinessCheckStatus.FAIL,
                    detail="Account state cannot be verified before account identity succeeds.",
                )
            )

        checks.append(self._market_clock_check())

        return StartupReadinessReport(
            provider=self._profile.provider,
            environment=self._profile.environment.value,
            account=self._profile.masked_account_id,
            checks=tuple(checks),
        )

    def _database_check(self) -> ReadinessCheck:
        try:
            healthy = self._database_probe()
        except Exception as exc:
            return ReadinessCheck(
                name="database",
                status=ReadinessCheckStatus.FAIL,
                detail=f"Database readiness probe failed ({type(exc).__name__}).",
            )

        return ReadinessCheck(
            name="database",
            status=(
                ReadinessCheckStatus.PASS if healthy else ReadinessCheckStatus.FAIL
            ),
            detail=(
                "PostgreSQL connectivity verified."
                if healthy
                else "PostgreSQL connectivity probe returned unhealthy."
            ),
        )

    def _account_identity_check(self) -> tuple[object | None, ReadinessCheck]:
        try:
            account = self._read_client.get_account()
        except Exception as exc:
            return None, ReadinessCheck(
                name="provider_account",
                status=ReadinessCheckStatus.FAIL,
                detail=f"Alpaca account query failed ({type(exc).__name__}).",
            )

        provider_account_id = str(getattr(account, "id", "")).strip()
        if provider_account_id != self._profile.expected_account_id:
            return account, ReadinessCheck(
                name="provider_account",
                status=ReadinessCheckStatus.FAIL,
                detail=(
                    "Alpaca account identity does not match the configured expected account."
                ),
            )

        return account, ReadinessCheck(
            name="provider_account",
            status=ReadinessCheckStatus.PASS,
            detail=f"Expected Alpaca account matched ({self._profile.masked_account_id}).",
        )

    @staticmethod
    def _account_state_check(account: object) -> ReadinessCheck:
        account_blocked = bool(getattr(account, "account_blocked", False))
        trading_blocked = bool(getattr(account, "trading_blocked", False))
        if account_blocked or trading_blocked:
            return ReadinessCheck(
                name="account_state",
                status=ReadinessCheckStatus.FAIL,
                detail="Alpaca account is blocked for account access or trading.",
            )
        return ReadinessCheck(
            name="account_state",
            status=ReadinessCheckStatus.PASS,
            detail="Alpaca account is not reported as account-blocked or trading-blocked.",
        )

    def _market_clock_check(self) -> ReadinessCheck:
        try:
            clock = self._read_client.get_clock()
        except Exception as exc:
            return ReadinessCheck(
                name="market_clock",
                status=ReadinessCheckStatus.FAIL,
                detail=f"Alpaca market clock query failed ({type(exc).__name__}).",
            )

        timestamp = getattr(clock, "timestamp", None)
        if timestamp is None:
            return ReadinessCheck(
                name="market_clock",
                status=ReadinessCheckStatus.FAIL,
                detail="Alpaca market clock did not expose a timestamp.",
            )
        return ReadinessCheck(
            name="market_clock",
            status=ReadinessCheckStatus.PASS,
            detail="Alpaca market clock received.",
        )


@dataclass(slots=True, repr=False)
class AlpacaPaperRuntimeComposition:
    """Constructed infrastructure required to begin the 0.5 PAPER runtime startup."""

    profile: RuntimeProfile
    manifest: ProviderManifest
    engine: Engine
    session_factory: sessionmaker[Session]
    read_client: TradingClient
    command_client: AlpacaPaperCommandClient
    market_data_client: StockHistoricalDataClient
    trade_stream: AlpacaPaperTradeStream
    readiness: AlpacaPaperStartupReadiness

    def __repr__(self) -> str:
        """Return a secret-safe diagnostic representation."""

        return (
            "AlpacaPaperRuntimeComposition("
            f"profile={self.profile!r}, "
            f"manifest={self.manifest.provider!r}, "
            "clients=<configured>, database=<configured>"
            ")"
        )


def build_alpaca_paper_runtime(
    profile: RuntimeProfile,
    secrets: SecretsPort,
    *,
    security: RuntimeSecurityConfig | None = None,
) -> AlpacaPaperRuntimeComposition:
    """Compose the frozen Alpaca PAPER bootstrap infrastructure."""

    _require_alpaca_paper_profile(profile)
    security_config = security or RuntimeSecurityConfig.local_development()

    api_key = secrets.resolve(profile.api_key_ref)
    secret_key = secrets.resolve(profile.api_secret_ref)
    database_url = secrets.resolve(profile.database_url_ref)

    engine = create_database_engine(
        database_url,
        require_tls=security_config.database_require_tls,
        connect_timeout_seconds=security_config.database_connect_timeout_seconds,
        statement_timeout_ms=security_config.database_statement_timeout_ms,
        pool_size=security_config.database_pool_size,
        max_overflow=security_config.database_max_overflow,
    )
    session_factory = create_session_factory(engine)
    read_client = TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True,
    )
    command_client = AlpacaPaperCommandClient(api_key, secret_key)
    market_data_client = StockHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key,
    )
    trade_stream = AlpacaPaperTradeStream(api_key, secret_key)
    manifest = build_alpaca_paper_manifest(profile)

    readiness = AlpacaPaperStartupReadiness(
        profile=profile,
        manifest=manifest,
        read_client=read_client,
        database_probe=lambda: database_is_healthy(engine),
    )

    return AlpacaPaperRuntimeComposition(
        profile=profile,
        manifest=manifest,
        engine=engine,
        session_factory=session_factory,
        read_client=read_client,
        command_client=command_client,
        market_data_client=market_data_client,
        trade_stream=trade_stream,
        readiness=readiness,
    )


def _require_alpaca_paper_profile(profile: RuntimeProfile) -> None:
    if profile.provider != ALPACA_PROVIDER_KEY:
        raise ValueError("Alpaca runtime composition requires provider 'alpaca'.")
    if profile.environment is not RuntimeEnvironment.PAPER:
        raise ValueError("Alpaca runtime composition is hard-locked to PAPER.")
    if profile.market_data_feed != "iex":
        raise ValueError("Alpaca runtime composition is hard-locked to the IEX feed.")
