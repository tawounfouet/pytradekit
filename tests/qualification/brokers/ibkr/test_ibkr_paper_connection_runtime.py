"""LOT-06.1 qualification for IBKR transport selection and PAPER startup."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ASYNC_VERSION_TARGET,
    IBKRPaperRuntimeProfile,
    IBKRTransportConnectionEvidence,
    build_ibkr_paper_connection_runtime,
)
from pytradekit.runtime import StartupReadinessState


class _QualifiedFakeTransport:
    def __init__(self) -> None:
        self.connected = False

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        self.connected = True
        return IBKRTransportConnectionEvidence(
            transport_name="ib_async",
            transport_version=IBKR_ASYNC_VERSION_TARGET,
            socket_connected=True,
            protocol_ready=True,
            account_verified=True,
            managed_accounts=(profile.expected_account_id,),
            server_version=178,
        )

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected


def test_lot06_1_reaches_startup_readiness_without_trading_claim() -> None:
    transport = _QualifiedFakeTransport()
    runtime = build_ibkr_paper_connection_runtime(
        IBKRPaperRuntimeProfile(expected_account_id="DU1234567"),
        transport=transport,
    )

    report = runtime.start()

    assert report.state is StartupReadinessState.READY_FOR_STARTUP
    assert report.to_dict()["trading_ready"] is False
    assert runtime.connection_evidence is not None
    assert runtime.connection_evidence.transport_version == "2.1.0"


def test_lot06_1_remains_paper_and_provider_local() -> None:
    profile = IBKRPaperRuntimeProfile(expected_account_id="DU1234567")

    assert profile.provider == "ibkr"
    assert profile.environment.value == "PAPER"
    assert profile.port == 4002
    assert profile.client_id.value != 0
