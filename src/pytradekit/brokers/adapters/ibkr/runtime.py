"""IBKR PAPER connection runtime backed by an optional ib_async transport."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from importlib import import_module, metadata
from math import isfinite
from typing import Protocol, cast

from pytradekit.brokers import (
    ProviderProtocolError,
    ProviderUnavailableError,
)
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    RuntimeEnvironment,
    StartupReadinessReport,
    mask_account_id,
)

from .discovery import (
    IBKR_PROVIDER_KEY,
    IBKRClientSurface,
    validate_ibkr_paper_port,
)
from .identities import IBKRClientId

IBKR_ASYNC_PACKAGE_NAME = "ib_async"
IBKR_ASYNC_VERSION_TARGET = "2.1.0"
IBKR_PAPER_RUNTIME_VERSION = "0.8.0b2-lot06.1"


class IBKRRuntimeConfigurationError(ValueError):
    """Raised when the provider-local IBKR runtime profile is unsafe."""


class IBKRRuntimeDependencyError(RuntimeError):
    """Raised when the selected optional transport dependency is unavailable."""


class _IBAsyncLowLevelClient(Protocol):
    def isReady(self) -> bool:
        """Return whether the API handshake has completed."""

        ...

    def serverVersion(self) -> int:
        """Return negotiated server version."""

        ...


class _IBAsyncClient(Protocol):
    @property
    def client(self) -> _IBAsyncLowLevelClient:
        """Return the synchronized low-level protocol client."""

        ...

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
        """Connect and synchronize with IB Gateway."""

        ...

    def disconnect(self) -> object:
        """Disconnect and clear session state."""

        ...

    def isConnected(self) -> bool:
        """Return whether the socket connection is active."""

        ...

    def managedAccounts(self) -> list[str]:
        """Return accounts visible to the connected API session."""

        ...

    def accountValues(self, account: str = "") -> list[object]:
        """Return synchronized account values."""

        ...

    def portfolio(self, account: str = "") -> list[object]:
        """Return synchronized portfolio rows."""

        ...

    def trades(self) -> list[object]:
        """Return synchronized trades from this session."""

        ...

    def fills(self) -> list[object]:
        """Return synchronized fills from this session."""

        ...


IBAsyncClientFactory = Callable[[], _IBAsyncClient]


class _IBAsyncReadClient(Protocol):
    def accountValues(self, account: str = "") -> list[object]:
        ...

    def portfolio(self, account: str = "") -> list[object]:
        ...

    def trades(self) -> list[object]:
        ...

    def fills(self) -> list[object]:
        ...


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRRuntimeConfigurationError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKRRuntimeConfigurationError(f"{field_name} must be non-empty.")
    return normalized


@dataclass(frozen=True, slots=True, repr=False)
class IBKRPaperRuntimeProfile:
    """Provider-local configuration for the first IB Gateway PAPER runtime."""

    expected_account_id: str
    host: str = "127.0.0.1"
    port: int = 4002
    client_id: IBKRClientId = field(default_factory=lambda: IBKRClientId(1))
    connect_timeout_seconds: float = 10.0
    name: str = "ibkr-paper"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected_account_id",
            _required_text(
                self.expected_account_id,
                field_name="expected_account_id",
            ),
        )
        normalized_host = _required_text(self.host, field_name="host").lower()
        if normalized_host not in {"127.0.0.1", "localhost"}:
            raise IBKRRuntimeConfigurationError(
                "LOT-06.1 IBKR PAPER runtime is hard-locked to a loopback host."
            )
        object.__setattr__(self, "host", normalized_host)

        validate_ibkr_paper_port(
            surface=IBKRClientSurface.IB_GATEWAY,
            port=self.port,
        )

        if not isinstance(self.client_id, IBKRClientId):
            raise IBKRRuntimeConfigurationError(
                "client_id must be an IBKRClientId."
            )
        if self.client_id.value == 0:
            raise IBKRRuntimeConfigurationError(
                "client_id 0 is forbidden because it can bind manual TWS orders."
            )

        timeout = self.connect_timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not isfinite(float(timeout))
            or float(timeout) <= 0
        ):
            raise IBKRRuntimeConfigurationError(
                "connect_timeout_seconds must be a finite positive number."
            )
        object.__setattr__(self, "connect_timeout_seconds", float(timeout))
        object.__setattr__(
            self,
            "name",
            _required_text(self.name, field_name="name"),
        )

    @property
    def provider(self) -> str:
        return IBKR_PROVIDER_KEY

    @property
    def environment(self) -> RuntimeEnvironment:
        return RuntimeEnvironment.PAPER

    @property
    def masked_account_id(self) -> str:
        return mask_account_id(self.expected_account_id)

    def __repr__(self) -> str:
        return (
            "IBKRPaperRuntimeProfile("
            f"name={self.name!r}, "
            f"host={self.host!r}, "
            f"port={self.port!r}, "
            f"client_id={self.client_id.value!r}, "
            f"expected_account_id={self.masked_account_id!r}, "
            f"connect_timeout_seconds={self.connect_timeout_seconds!r}"
            ")"
        )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> IBKRPaperRuntimeProfile:
        """Build the provider-local PAPER profile from environment values."""

        source = os.environ if environ is None else environ

        expected_account_id = source.get(
            "PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID",
            "",
        )
        host = source.get("PYTRADEKIT_IBKR_HOST", "127.0.0.1")
        port = _parse_int(
            source.get("PYTRADEKIT_IBKR_PORT", "4002"),
            field_name="PYTRADEKIT_IBKR_PORT",
        )
        client_id = _parse_int(
            source.get("PYTRADEKIT_IBKR_CLIENT_ID", "1"),
            field_name="PYTRADEKIT_IBKR_CLIENT_ID",
        )
        timeout = _parse_float(
            source.get("PYTRADEKIT_IBKR_CONNECT_TIMEOUT_SECONDS", "10"),
            field_name="PYTRADEKIT_IBKR_CONNECT_TIMEOUT_SECONDS",
        )

        return cls(
            name=source.get("PYTRADEKIT_RUNTIME_PROFILE", "ibkr-paper"),
            expected_account_id=expected_account_id,
            host=host,
            port=port,
            client_id=IBKRClientId(client_id),
            connect_timeout_seconds=timeout,
        )


@dataclass(frozen=True, slots=True)
class IBKRTransportConnectionEvidence:
    """Sanitized evidence from one synchronized IB Gateway connection."""

    transport_name: str
    transport_version: str
    socket_connected: bool
    protocol_ready: bool
    account_verified: bool
    managed_accounts: tuple[str, ...]
    server_version: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transport_name",
            _required_text(self.transport_name, field_name="transport_name"),
        )
        object.__setattr__(
            self,
            "transport_version",
            _required_text(
                self.transport_version,
                field_name="transport_version",
            ),
        )
        for field_name in (
            "socket_connected",
            "protocol_ready",
            "account_verified",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKRRuntimeConfigurationError(f"{field_name} must be a bool.")
        if any(not account.strip() for account in self.managed_accounts):
            raise IBKRRuntimeConfigurationError(
                "managed_accounts must not contain blank values."
            )
        if self.server_version is not None and (
            type(self.server_version) is not int or self.server_version <= 0
        ):
            raise IBKRRuntimeConfigurationError(
                "server_version must be a positive int or None."
            )

    @property
    def synchronized(self) -> bool:
        return (
            self.socket_connected
            and self.protocol_ready
            and self.account_verified
        )


class IBKRTransportPort(Protocol):
    """Provider-local transport boundary used by the PAPER runtime."""

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        """Connect and return synchronized transport evidence."""

        ...

    def disconnect(self) -> None:
        """Disconnect the provider transport."""

        ...

    def is_connected(self) -> bool:
        """Return whether the provider socket remains connected."""

        ...

    def read_client(self) -> object:
        """Return the synchronized provider client for provider-local reads."""

        ...

    def accountValues(self, account: str = "") -> list[object]:
        """Return synchronized provider account values."""

        ...

    def portfolio(self, account: str = "") -> list[object]:
        """Return synchronized provider portfolio rows."""

        ...

    def trades(self) -> list[object]:
        """Return synchronized provider trades."""

        ...

    def fills(self) -> list[object]:
        """Return synchronized provider fills."""

        ...


class IBAsyncPaperTransport:
    """ib_async-backed IB Gateway PAPER transport with fail-closed validation."""

    def __init__(
        self,
        *,
        client_factory: IBAsyncClientFactory | None = None,
        package_version: str | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._package_version_override = package_version
        self._client: _IBAsyncClient | None = None

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        if not isinstance(profile, IBKRPaperRuntimeProfile):
            raise IBKRRuntimeConfigurationError(
                "profile must be an IBKRPaperRuntimeProfile."
            )
        if self.is_connected():
            raise ProviderProtocolError(
                "IBKR transport is already connected.",
                provider=IBKR_PROVIDER_KEY,
                operation="connect",
            )

        factory, package_version = self._resolve_factory()
        client = factory()
        self._client = client

        try:
            client.connect(
                profile.host,
                profile.port,
                profile.client_id.value,
                profile.connect_timeout_seconds,
                False,
                profile.expected_account_id,
                True,
            )
            socket_connected = bool(client.isConnected())
            protocol_ready = bool(client.client.isReady())
            managed_accounts = tuple(
                sorted(
                    account.strip()
                    for account in client.managedAccounts()
                    if account.strip()
                )
            )
            account_verified = (
                profile.expected_account_id in managed_accounts
            )
            server_version = client.client.serverVersion()
        except Exception as exc:
            self._safe_disconnect()
            raise ProviderUnavailableError(
                f"IBKR PAPER connection failed ({type(exc).__name__}).",
                provider=IBKR_PROVIDER_KEY,
                operation="connect",
            ) from exc

        if not socket_connected:
            self._safe_disconnect()
            raise ProviderUnavailableError(
                "IBKR PAPER socket did not remain connected.",
                provider=IBKR_PROVIDER_KEY,
                operation="connect",
            )
        if not protocol_ready:
            self._safe_disconnect()
            raise ProviderProtocolError(
                "IBKR API handshake did not reach protocol readiness.",
                provider=IBKR_PROVIDER_KEY,
                operation="connect",
            )
        if not account_verified:
            self._safe_disconnect()
            raise ProviderProtocolError(
                "IBKR account identity does not match the configured PAPER account.",
                provider=IBKR_PROVIDER_KEY,
                operation="connect",
            )

        return IBKRTransportConnectionEvidence(
            transport_name=IBKR_ASYNC_PACKAGE_NAME,
            transport_version=package_version,
            socket_connected=socket_connected,
            protocol_ready=protocol_ready,
            account_verified=account_verified,
            managed_accounts=managed_accounts,
            server_version=server_version,
        )

    def disconnect(self) -> None:
        self._safe_disconnect()

    def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(self._client.isConnected())
        except Exception:
            return False

    def accountValues(self, account: str = "") -> list[object]:
        """Return synchronized account values from the connected session."""

        client = cast(_IBAsyncReadClient, self._require_connected_client())
        return list(client.accountValues(account))

    def portfolio(self, account: str = "") -> list[object]:
        """Return synchronized portfolio items from the connected session."""

        client = cast(_IBAsyncReadClient, self._require_connected_client())
        return list(client.portfolio(account))

    def trades(self) -> list[object]:
        """Return synchronized open and completed trades from the session."""

        client = cast(_IBAsyncReadClient, self._require_connected_client())
        return list(client.trades())

    def fills(self) -> list[object]:
        """Return synchronized fills from the connected session."""

        client = cast(_IBAsyncReadClient, self._require_connected_client())
        return list(client.fills())

    def _require_connected_client(self) -> _IBAsyncClient:
        client = self._client
        if client is None or not self.is_connected():
            raise ProviderUnavailableError(
                "IBKR PAPER read-side requires an active connection.",
                provider=IBKR_PROVIDER_KEY,
                operation="read_side",
            )
        return client

    def read_client(self) -> object:
        """Return the connected provider-local read client."""

        return self._require_connected_client()

    def _resolve_factory(self) -> tuple[IBAsyncClientFactory, str]:
        if self._client_factory is not None:
            package_version = (
                self._package_version_override or IBKR_ASYNC_VERSION_TARGET
            )
            if package_version != IBKR_ASYNC_VERSION_TARGET:
                raise IBKRRuntimeDependencyError(
                    "Injected ib_async transport version does not match the pinned target."
                )
            return self._client_factory, package_version

        try:
            installed_version = metadata.version(IBKR_ASYNC_PACKAGE_NAME)
        except metadata.PackageNotFoundError as exc:
            raise IBKRRuntimeDependencyError(
                "ib_async is not installed; install PyTradeKit with the ibkr extra."
            ) from exc

        if installed_version != IBKR_ASYNC_VERSION_TARGET:
            raise IBKRRuntimeDependencyError(
                "Installed ib_async version does not match the qualified transport pin."
            )

        try:
            module = import_module(IBKR_ASYNC_PACKAGE_NAME)
            client_type = module.IB
        except (ImportError, AttributeError) as exc:
            raise IBKRRuntimeDependencyError(
                "ib_async does not expose the expected IB transport class."
            ) from exc

        def factory() -> _IBAsyncClient:
            return cast(_IBAsyncClient, client_type())

        return factory, installed_version

    def _safe_disconnect(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            client.disconnect()
        except Exception:
            return


@dataclass(slots=True)
class IBKRPaperConnectionRuntime:
    """LOT-06.1 provider-local startup composition for IB Gateway PAPER."""

    profile: IBKRPaperRuntimeProfile
    transport: IBKRTransportPort
    connection_evidence: IBKRTransportConnectionEvidence | None = None

    def start(self) -> StartupReadinessReport:
        """Connect, verify startup identity, and avoid any trading-ready claim."""

        try:
            evidence = self.transport.connect(self.profile)
        except Exception as exc:
            self.connection_evidence = None
            return StartupReadinessReport(
                provider=IBKR_PROVIDER_KEY,
                environment=RuntimeEnvironment.PAPER.value,
                account=self.profile.masked_account_id,
                checks=(
                    ReadinessCheck(
                        name="profile",
                        status=ReadinessCheckStatus.PASS,
                        detail="IBKR PAPER runtime profile validated.",
                    ),
                    ReadinessCheck(
                        name="transport",
                        status=ReadinessCheckStatus.FAIL,
                        detail=(
                            "IBKR PAPER transport connection failed "
                            f"({type(exc).__name__})."
                        ),
                    ),
                ),
            )

        self.connection_evidence = evidence
        return StartupReadinessReport(
            provider=IBKR_PROVIDER_KEY,
            environment=RuntimeEnvironment.PAPER.value,
            account=self.profile.masked_account_id,
            checks=(
                ReadinessCheck(
                    name="profile",
                    status=ReadinessCheckStatus.PASS,
                    detail="IBKR PAPER runtime profile validated.",
                ),
                ReadinessCheck(
                    name="transport_package",
                    status=ReadinessCheckStatus.PASS,
                    detail=(
                        f"{evidence.transport_name}=="
                        f"{evidence.transport_version} selected."
                    ),
                ),
                ReadinessCheck(
                    name="paper_endpoint",
                    status=ReadinessCheckStatus.PASS,
                    detail="IB Gateway PAPER port 4002 validated.",
                ),
                ReadinessCheck(
                    name="socket",
                    status=(
                        ReadinessCheckStatus.PASS
                        if evidence.socket_connected
                        else ReadinessCheckStatus.FAIL
                    ),
                    detail="IBKR socket connection verified.",
                ),
                ReadinessCheck(
                    name="protocol",
                    status=(
                        ReadinessCheckStatus.PASS
                        if evidence.protocol_ready
                        else ReadinessCheckStatus.FAIL
                    ),
                    detail="IBKR protocol handshake and nextValidId readiness verified.",
                ),
                ReadinessCheck(
                    name="provider_account",
                    status=(
                        ReadinessCheckStatus.PASS
                        if evidence.account_verified
                        else ReadinessCheckStatus.FAIL
                    ),
                    detail=(
                        "Expected IBKR PAPER account matched "
                        f"({self.profile.masked_account_id})."
                    ),
                ),
            ),
        )

    def read_client(self) -> object:
        """Return the connected provider-local read client."""

        if self.connection_evidence is None:
            raise ProviderUnavailableError(
                "IBKR PAPER runtime has not completed startup.",
                provider=IBKR_PROVIDER_KEY,
                operation="read_client",
            )
        return self.transport.read_client()

    def stop(self) -> None:
        self.transport.disconnect()
        self.connection_evidence = None


def build_ibkr_paper_connection_runtime(
    profile: IBKRPaperRuntimeProfile,
    *,
    transport: IBKRTransportPort | None = None,
) -> IBKRPaperConnectionRuntime:
    """Compose the LOT-06.1 provider-local IBKR PAPER connection runtime."""

    if not isinstance(profile, IBKRPaperRuntimeProfile):
        raise IBKRRuntimeConfigurationError(
            "profile must be an IBKRPaperRuntimeProfile."
        )
    return IBKRPaperConnectionRuntime(
        profile=profile,
        transport=transport or IBAsyncPaperTransport(),
    )


def _parse_int(value: str, *, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IBKRRuntimeConfigurationError(
            f"{field_name} must be an integer."
        ) from exc


def _parse_float(value: str, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise IBKRRuntimeConfigurationError(
            f"{field_name} must be a number."
        ) from exc
