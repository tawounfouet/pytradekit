"""Unit tests for the IBKR LOT-06.1 PAPER connection runtime."""

import pytest

from pytradekit.brokers import ProviderProtocolError, ProviderUnavailableError
from pytradekit.brokers.adapters.ibkr import (
    IBKR_ASYNC_VERSION_TARGET,
    IBAsyncPaperTransport,
    IBKRClientId,
    IBKRPaperRuntimeProfile,
    IBKRRuntimeConfigurationError,
    build_ibkr_paper_connection_runtime,
)
from pytradekit.runtime import StartupReadinessState


class _FakeLowLevelClient:
    def __init__(self, *, ready: bool = True, server_version: int = 178) -> None:
        self.ready = ready
        self.server_version = server_version

    def isReady(self) -> bool:
        return self.ready

    def serverVersion(self) -> int:
        return self.server_version


class _FakeIBClient:
    def __init__(
        self,
        *,
        accounts: list[str] | None = None,
        ready: bool = True,
        connect_error: Exception | None = None,
    ) -> None:
        self.client = _FakeLowLevelClient(ready=ready)
        self.accounts = accounts or ["DU1234567"]
        self.connect_error = connect_error
        self.connected = False
        self.disconnected = False
        self.connect_args: tuple[object, ...] | None = None

    def connect(
        self,
        host: str,
        port: int,
        clientId: int,
        timeout: float,
        readonly: bool,
        account: str,
        raiseSyncErrors: bool,
    ) -> object:
        self.connect_args = (
            host,
            port,
            clientId,
            timeout,
            readonly,
            account,
            raiseSyncErrors,
        )
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True
        return self

    def disconnect(self) -> object:
        self.connected = False
        self.disconnected = True
        return None

    def isConnected(self) -> bool:
        return self.connected

    def managedAccounts(self) -> list[str]:
        return list(self.accounts)

    def accountValues(self, account: str = "") -> list[object]:
        return [f"account:{account}"]

    def portfolio(self, account: str = "") -> list[object]:
        return [f"portfolio:{account}"]

    def trades(self) -> list[object]:
        return ["trade"]

    def fills(self) -> list[object]:
        return ["fill"]


def _profile() -> IBKRPaperRuntimeProfile:
    return IBKRPaperRuntimeProfile(
        expected_account_id="DU1234567",
        client_id=IBKRClientId(1),
    )


def test_profile_is_hard_locked_to_ib_gateway_paper() -> None:
    profile = _profile()

    assert profile.provider == "ibkr"
    assert profile.environment.value == "PAPER"
    assert profile.host == "127.0.0.1"
    assert profile.port == 4002
    assert profile.client_id.value == 1


def test_profile_rejects_live_gateway_port() -> None:
    with pytest.raises(ValueError, match="LIVE"):
        IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            port=4001,
        )


def test_profile_rejects_non_loopback_host() -> None:
    with pytest.raises(IBKRRuntimeConfigurationError, match="loopback"):
        IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            host="10.0.0.10",
        )


def test_profile_rejects_client_zero_to_avoid_manual_order_binding() -> None:
    with pytest.raises(IBKRRuntimeConfigurationError, match="client_id 0"):
        IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(0),
        )


def test_profile_repr_masks_account_identity() -> None:
    rendered = repr(_profile())

    assert "DU1234567" not in rendered
    assert "***4567" in rendered


def test_profile_from_environment_uses_provider_local_settings() -> None:
    profile = IBKRPaperRuntimeProfile.from_environment(
        {
            "PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID": "DU1234567",
            "PYTRADEKIT_IBKR_HOST": "localhost",
            "PYTRADEKIT_IBKR_PORT": "4002",
            "PYTRADEKIT_IBKR_CLIENT_ID": "7",
            "PYTRADEKIT_IBKR_CONNECT_TIMEOUT_SECONDS": "4.5",
        }
    )

    assert profile.host == "localhost"
    assert profile.port == 4002
    assert profile.client_id.value == 7
    assert profile.connect_timeout_seconds == 4.5


def test_ib_async_transport_uses_frozen_connection_parameters() -> None:
    client = _FakeIBClient()
    transport = IBAsyncPaperTransport(
        client_factory=lambda: client,
        package_version=IBKR_ASYNC_VERSION_TARGET,
    )

    evidence = transport.connect(_profile())

    assert client.connect_args == (
        "127.0.0.1",
        4002,
        1,
        10.0,
        False,
        "DU1234567",
        True,
    )
    assert evidence.socket_connected
    assert evidence.protocol_ready
    assert evidence.account_verified
    assert evidence.server_version == 178
    assert transport.is_connected()


def test_account_identity_mismatch_fails_closed_and_disconnects() -> None:
    client = _FakeIBClient(accounts=["DU9999999"])
    transport = IBAsyncPaperTransport(
        client_factory=lambda: client,
        package_version=IBKR_ASYNC_VERSION_TARGET,
    )

    with pytest.raises(ProviderProtocolError, match="account identity"):
        transport.connect(_profile())

    assert client.disconnected
    assert not transport.is_connected()


def test_protocol_not_ready_fails_closed() -> None:
    client = _FakeIBClient(ready=False)
    transport = IBAsyncPaperTransport(
        client_factory=lambda: client,
        package_version=IBKR_ASYNC_VERSION_TARGET,
    )

    with pytest.raises(ProviderProtocolError, match="protocol readiness"):
        transport.connect(_profile())

    assert client.disconnected


def test_connection_exception_is_sanitized_as_provider_unavailable() -> None:
    client = _FakeIBClient(connect_error=ConnectionRefusedError("secret path"))
    transport = IBAsyncPaperTransport(
        client_factory=lambda: client,
        package_version=IBKR_ASYNC_VERSION_TARGET,
    )

    with pytest.raises(ProviderUnavailableError) as captured:
        transport.connect(_profile())

    assert "secret path" not in str(captured.value)
    assert "ConnectionRefusedError" in str(captured.value)


def test_connection_runtime_reports_startup_ready_without_trading_ready_claim() -> None:
    client = _FakeIBClient()
    runtime = build_ibkr_paper_connection_runtime(
        _profile(),
        transport=IBAsyncPaperTransport(
            client_factory=lambda: client,
            package_version=IBKR_ASYNC_VERSION_TARGET,
        ),
    )

    report = runtime.start()

    assert report.state is StartupReadinessState.READY_FOR_STARTUP
    assert report.ready_for_startup
    assert report.to_dict()["trading_ready"] is False
    assert runtime.connection_evidence is not None

    runtime.stop()
    assert not client.connected
    assert runtime.connection_evidence is None


def test_connection_runtime_returns_not_ready_on_transport_failure() -> None:
    client = _FakeIBClient(connect_error=ConnectionRefusedError())
    runtime = build_ibkr_paper_connection_runtime(
        _profile(),
        transport=IBAsyncPaperTransport(
            client_factory=lambda: client,
            package_version=IBKR_ASYNC_VERSION_TARGET,
        ),
    )

    report = runtime.start()

    assert report.state is StartupReadinessState.NOT_READY
    assert not report.ready_for_startup
    assert runtime.connection_evidence is None


def test_transport_forwards_synchronized_read_side_after_connect() -> None:
    client = _FakeIBClient()
    transport = IBAsyncPaperTransport(
        client_factory=lambda: client,
        package_version=IBKR_ASYNC_VERSION_TARGET,
    )
    transport.connect(_profile())

    assert transport.accountValues("DU1234567") == ["account:DU1234567"]
    assert transport.portfolio("DU1234567") == ["portfolio:DU1234567"]
    assert transport.trades() == ["trade"]
    assert transport.fills() == ["fill"]


def test_transport_read_side_fails_closed_when_disconnected() -> None:
    transport = IBAsyncPaperTransport(
        client_factory=_FakeIBClient,
        package_version=IBKR_ASYNC_VERSION_TARGET,
    )

    with pytest.raises(ProviderUnavailableError, match="active connection"):
        transport.accountValues("DU1234567")
