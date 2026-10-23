"""Unit tests for IBKR LOT-06.6 operational containment."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from pytradekit.brokers import (
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderStateReconciliationRequired,
    ProviderUnavailableError,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRErrorObservation,
    IBKROperationalGuard,
    IBKRPaperConnectionRuntime,
    IBKRPaperRuntimeProfile,
    IBKRReconnectRecoveryRuntime,
    IBKRTransportConnectionEvidence,
    build_ibkr_operational_runtime,
    qualify_ib_async_pacing,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application import ReconciliationOutcome
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    StateConfidence,
)
from pytradekit.shared import CorrelationId

_NOW = datetime(2026, 10, 23, 10, 45, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Event:
    def __init__(self) -> None:
        self.listeners: list[Callable[..., object]] = []

    def connect(
        self,
        listener: Callable[..., object],
        error: object | None = None,
        done: object | None = None,
        keep_ref: bool = False,
    ) -> object:
        _ = (error, done, keep_ref)
        self.listeners.append(listener)
        return listener

    def disconnect(self, listener: Callable[..., object]) -> object:
        if listener in self.listeners:
            self.listeners.remove(listener)
        return listener

    def emit(self, *args: object) -> None:
        for listener in tuple(self.listeners):
            listener(*args)


class _LowLevel:
    def __init__(
        self,
        *,
        max_requests: int = 45,
        interval: float = 1.0,
    ) -> None:
        self.MaxRequests = max_requests
        self.RequestsInterval = interval
        self.throttleStart = _Event()
        self.throttleEnd = _Event()


class _Provider:
    def __init__(self) -> None:
        self.client = _LowLevel()
        self.connectedEvent = _Event()
        self.disconnectedEvent = _Event()
        self.errorEvent = _Event()


class _Transport:
    def __init__(self, provider: _Provider) -> None:
        self.provider = provider
        self.connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        self.connect_calls += 1
        self.connected = True
        return IBKRTransportConnectionEvidence(
            transport_name="deterministic",
            transport_version="2.1.0",
            socket_connected=True,
            protocol_ready=True,
            account_verified=True,
            managed_accounts=(profile.expected_account_id,),
            server_version=200,
        )

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def read_client(self) -> object:
        if not self.connected:
            raise RuntimeError("disconnected")
        return self.provider


class _Reconciliation:
    def __init__(
        self,
        *,
        status: ConsistencyStatus = ConsistencyStatus.CONSISTENT,
        confidence: StateConfidence = StateConfidence.HIGH,
    ) -> None:
        self.status = status
        self.confidence = confidence
        self.calls = 0

    def reconnect(self) -> ReconciliationOutcome:
        self.calls += 1
        run = ReconciliationRun.create(
            account_id=AccountId.new(),
            scope=ReconciliationScope.FULL,
            trigger=ReconciliationTrigger.RECONNECT,
            started_at=_NOW,
            correlation_id=CorrelationId.new(),
        )
        run.transition_to(ReconciliationRunStatus.CAPTURING)
        run.transition_to(ReconciliationRunStatus.COMPARING)
        run.complete(
            completed_at=_NOW,
            result_status=self.status,
            confidence=self.confidence,
            mismatch_count=0,
            critical_mismatch_count=0,
        )
        return ReconciliationOutcome(
            run=run,
            mismatches=(),
            resolutions=(),
        )


def _connection() -> tuple[
    IBKRPaperConnectionRuntime,
    _Provider,
    _Transport,
]:
    provider = _Provider()
    transport = _Transport(provider)
    connection = IBKRPaperConnectionRuntime(
        profile=IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(7),
        ),
        transport=transport,
    )
    assert connection.start().ready_for_startup
    return connection, provider, transport


def _error(code: int) -> IBKRErrorObservation:
    return IBKRErrorObservation(
        request_id=-1,
        code=code,
        message=f"provider code {code}",
        observed_at=_NOW,
    )


def test_ib_async_default_pacing_is_within_qualified_ceiling() -> None:
    evidence = qualify_ib_async_pacing(_LowLevel())

    assert evidence.max_requests == 45
    assert evidence.requests_interval_seconds == 1.0
    assert evidence.effective_rate_per_second == 45.0


def test_pacing_configuration_above_ceiling_fails_closed() -> None:
    with pytest.raises(
        ProviderProtocolError,
        match="request rate exceeds",
    ):
        qualify_ib_async_pacing(
            _LowLevel(max_requests=46, interval=1.0)
        )


def test_transport_throttle_temporarily_blocks_economic_writes() -> None:
    connection, provider, _transport = _connection()
    runtime = build_ibkr_operational_runtime(
        connection=connection,
        reconciliation_complete=True,
        clock=_Clock(),
    )

    provider.client.throttleStart.emit()
    with pytest.raises(ProviderRateLimitError):
        runtime.guard.require_write_allowed(operation="submit")

    provider.client.throttleEnd.emit()
    runtime.guard.require_write_allowed(operation="submit")


def test_code_100_latches_pacing_until_explicit_recovery() -> None:
    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )

    mapped = guard.observe_error(
        _error(100),
        operation="submit",
    )

    assert isinstance(mapped, ProviderRateLimitError)
    with pytest.raises(ProviderRateLimitError):
        guard.require_write_allowed(operation="submit")

    guard.mark_pacing_recovered()
    guard.require_write_allowed(operation="submit")


def test_standalone_1102_preserves_existing_safe_reconciliation() -> None:
    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )

    mapped = guard.observe_error(
        _error(1102),
        operation="provider_event",
    )

    assert mapped is None
    assert guard.snapshot.reconciliation_complete
    guard.require_write_allowed(operation="submit")


def test_1100_then_1102_still_requires_reconciliation() -> None:
    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )

    guard.observe_error(_error(1100), operation="provider_event")
    with pytest.raises(ProviderUnavailableError):
        guard.require_write_allowed(operation="submit")

    guard.observe_error(_error(1102), operation="provider_event")
    with pytest.raises(ProviderStateReconciliationRequired):
        guard.require_write_allowed(operation="submit")

    guard.mark_reconciled()
    guard.require_write_allowed(operation="submit")


def test_1101_requires_market_data_resubscription_but_not_write_replay() -> None:
    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )

    guard.observe_error(_error(1100), operation="provider_event")
    guard.observe_error(_error(1101), operation="provider_event")
    state = guard.snapshot

    assert state.market_data_resubscription_required
    assert not state.reconciliation_complete

    guard.mark_reconciled()
    guard.require_write_allowed(operation="submit")
    with pytest.raises(ProviderUnavailableError):
        guard.require_market_data_allowed(operation="quote")

    guard.mark_market_data_resubscribed()
    guard.require_market_data_allowed(operation="quote")


def test_2103_degrades_market_data_without_globally_blocking_writes() -> None:
    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )

    guard.observe_error(_error(2103), operation="provider_event")

    guard.require_write_allowed(operation="submit")
    with pytest.raises(ProviderUnavailableError):
        guard.require_market_data_allowed(operation="quote")


def test_disconnected_event_blocks_until_reconnect_and_reconciliation() -> None:
    connection, provider, _transport = _connection()
    runtime = build_ibkr_operational_runtime(
        connection=connection,
        reconciliation_complete=True,
        clock=_Clock(),
    )

    provider.disconnectedEvent.emit()

    assert runtime.guard.snapshot.reconnect_required
    with pytest.raises(ProviderUnavailableError):
        runtime.guard.require_write_allowed(operation="submit")


def test_explicit_socket_recovery_rebinds_then_reconciles() -> None:
    connection, _provider, transport = _connection()
    runtime = build_ibkr_operational_runtime(
        connection=connection,
        reconciliation_complete=True,
        clock=_Clock(),
    )
    runtime.guard.observe_error(
        _error(1300),
        operation="provider_event",
    )
    assert runtime.guard.snapshot.reconnect_required
    reconciliation = _Reconciliation()
    recovery = IBKRReconnectRecoveryRuntime(
        connection=connection,
        operations=runtime,
        reconciliation=reconciliation,
    )

    evidence = recovery.recover(reconnect_socket=True)

    assert evidence.socket_reconnected
    assert evidence.reconciliation_ran
    assert evidence.reconciliation_safe
    assert reconciliation.calls == 1
    assert transport.connect_calls == 2
    assert transport.disconnect_calls == 1
    runtime.guard.require_write_allowed(operation="submit")


def test_unsafe_reconciliation_keeps_writes_closed() -> None:
    connection, _provider, _transport = _connection()
    runtime = build_ibkr_operational_runtime(
        connection=connection,
        reconciliation_complete=False,
        clock=_Clock(),
    )
    reconciliation = _Reconciliation(
        status=ConsistencyStatus.INCONSISTENT,
        confidence=StateConfidence.LOW,
    )
    recovery = IBKRReconnectRecoveryRuntime(
        connection=connection,
        operations=runtime,
        reconciliation=reconciliation,
    )

    evidence = recovery.recover(reconnect_socket=False)

    assert evidence.reconciliation_ran
    assert not evidence.reconciliation_safe
    with pytest.raises(ProviderStateReconciliationRequired):
        runtime.guard.require_write_allowed(operation="submit")
