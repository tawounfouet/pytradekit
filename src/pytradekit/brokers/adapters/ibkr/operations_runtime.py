"""IBKR pacing, connectivity containment, and reconnect recovery runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import Protocol, cast

from pytradekit.brokers import (
    ProviderError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderStateReconciliationRequired,
    ProviderUnavailableError,
)
from pytradekit.reconciliation.application import ReconciliationOutcome
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    StateConfidence,
)
from pytradekit.runtime.ports import ClockPort

from .discovery import IBKR_PROVIDER_KEY
from .error_readiness import (
    IBKRErrorObservation,
    map_ibkr_provider_error,
)
from .runtime import IBKRPaperConnectionRuntime

IBKR_OPERATIONAL_RUNTIME_VERSION = "0.8.0b7-lot06.6"
IBKR_QUALIFIED_MAX_REQUEST_RATE_PER_SECOND = 45.0


class IBKROperationalRuntimeError(ValueError):
    """Raised when operational runtime evidence is invalid."""


class _EventLike(Protocol):
    def connect(
        self,
        listener: Callable[..., object],
        error: object | None = None,
        done: object | None = None,
        keep_ref: bool = False,
    ) -> object:
        ...

    def disconnect(self, listener: Callable[..., object]) -> object:
        ...


class _LowLevelOperationalClient(Protocol):
    MaxRequests: int
    RequestsInterval: float
    throttleStart: _EventLike
    throttleEnd: _EventLike


class _OperationalClient(Protocol):
    client: _LowLevelOperationalClient
    connectedEvent: _EventLike
    disconnectedEvent: _EventLike
    errorEvent: _EventLike


class IBKRReconnectReconciliation(Protocol):
    """Reconciliation surface required after provider connectivity recovery."""

    def reconnect(self) -> ReconciliationOutcome:
        """Reconcile canonical and provider state after connectivity recovery."""

        ...


@dataclass(frozen=True, slots=True)
class IBKRPacingEvidence:
    """Qualified ib_async request-throttling configuration."""

    max_requests: int
    requests_interval_seconds: float
    effective_rate_per_second: float

    def __post_init__(self) -> None:
        if type(self.max_requests) is not int or self.max_requests <= 0:
            raise IBKROperationalRuntimeError(
                "max_requests must be a positive int."
            )
        if (
            isinstance(self.requests_interval_seconds, bool)
            or not isinstance(self.requests_interval_seconds, (int, float))
            or not isfinite(float(self.requests_interval_seconds))
            or float(self.requests_interval_seconds) <= 0
        ):
            raise IBKROperationalRuntimeError(
                "requests_interval_seconds must be a finite positive number."
            )
        if (
            isinstance(self.effective_rate_per_second, bool)
            or not isinstance(self.effective_rate_per_second, (int, float))
            or not isfinite(float(self.effective_rate_per_second))
            or float(self.effective_rate_per_second) <= 0
        ):
            raise IBKROperationalRuntimeError(
                "effective_rate_per_second must be a finite positive number."
            )


@dataclass(frozen=True, slots=True)
class IBKROperationalSnapshot:
    """Current provider-local containment state."""

    socket_connected: bool
    provider_connected: bool
    reconciliation_complete: bool
    market_data_ready: bool
    market_data_resubscription_required: bool
    reconnect_required: bool
    transport_throttle_active: bool
    pacing_violation_latched: bool
    fail_closed_latched: bool
    last_provider_code: int | None

    def __post_init__(self) -> None:
        for field_name in (
            "socket_connected",
            "provider_connected",
            "reconciliation_complete",
            "market_data_ready",
            "market_data_resubscription_required",
            "reconnect_required",
            "transport_throttle_active",
            "pacing_violation_latched",
            "fail_closed_latched",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKROperationalRuntimeError(
                    f"{field_name} must be a bool."
                )
        if self.last_provider_code is not None and (
            type(self.last_provider_code) is not int
            or self.last_provider_code <= 0
        ):
            raise IBKROperationalRuntimeError(
                "last_provider_code must be a positive int or None."
            )

    @property
    def write_allowed(self) -> bool:
        return (
            self.socket_connected
            and self.provider_connected
            and self.reconciliation_complete
            and not self.reconnect_required
            and not self.transport_throttle_active
            and not self.pacing_violation_latched
            and not self.fail_closed_latched
        )

    @property
    def market_data_allowed(self) -> bool:
        return (
            self.socket_connected
            and self.provider_connected
            and self.market_data_ready
            and not self.market_data_resubscription_required
            and not self.fail_closed_latched
        )


class IBKROperationalGuard:
    """Stateful fail-closed gate for pacing and provider connectivity."""

    def __init__(
        self,
        *,
        socket_connected: bool,
        provider_connected: bool,
        reconciliation_complete: bool,
        market_data_ready: bool = True,
    ) -> None:
        for field_name, value in (
            ("socket_connected", socket_connected),
            ("provider_connected", provider_connected),
            ("reconciliation_complete", reconciliation_complete),
            ("market_data_ready", market_data_ready),
        ):
            if type(value) is not bool:
                raise IBKROperationalRuntimeError(
                    f"{field_name} must be a bool."
                )
        self._socket_connected = socket_connected
        self._provider_connected = provider_connected
        self._reconciliation_complete = reconciliation_complete
        self._market_data_ready = market_data_ready
        self._market_data_resubscription_required = False
        self._reconnect_required = not socket_connected
        self._transport_throttle_active = False
        self._pacing_violation_latched = False
        self._fail_closed_latched = False
        self._last_provider_code: int | None = None

    @property
    def snapshot(self) -> IBKROperationalSnapshot:
        return IBKROperationalSnapshot(
            socket_connected=self._socket_connected,
            provider_connected=self._provider_connected,
            reconciliation_complete=self._reconciliation_complete,
            market_data_ready=self._market_data_ready,
            market_data_resubscription_required=(
                self._market_data_resubscription_required
            ),
            reconnect_required=self._reconnect_required,
            transport_throttle_active=self._transport_throttle_active,
            pacing_violation_latched=self._pacing_violation_latched,
            fail_closed_latched=self._fail_closed_latched,
            last_provider_code=self._last_provider_code,
        )

    def require_write_allowed(self, *, operation: str) -> None:
        normalized_operation = _required_text(operation, field_name="operation")
        state = self.snapshot
        if state.fail_closed_latched:
            raise ProviderProtocolError(
                "IBKR operational runtime is fail-closed after an unknown provider state.",
                provider=IBKR_PROVIDER_KEY,
                operation=normalized_operation,
                provider_code=(
                    str(state.last_provider_code)
                    if state.last_provider_code is not None
                    else None
                ),
            )
        if state.transport_throttle_active or state.pacing_violation_latched:
            raise ProviderRateLimitError(
                "IBKR pacing containment blocks economic writes.",
                provider=IBKR_PROVIDER_KEY,
                operation=normalized_operation,
                provider_code=(
                    str(state.last_provider_code)
                    if state.last_provider_code is not None
                    else None
                ),
            )
        if (
            not state.socket_connected
            or not state.provider_connected
            or state.reconnect_required
        ):
            raise ProviderUnavailableError(
                "IBKR connectivity is not healthy for economic writes.",
                provider=IBKR_PROVIDER_KEY,
                operation=normalized_operation,
                provider_code=(
                    str(state.last_provider_code)
                    if state.last_provider_code is not None
                    else None
                ),
            )
        if not state.reconciliation_complete:
            raise ProviderStateReconciliationRequired(
                "IBKR reconciliation must complete before economic writes resume.",
                provider=IBKR_PROVIDER_KEY,
                operation=normalized_operation,
                provider_code=(
                    str(state.last_provider_code)
                    if state.last_provider_code is not None
                    else None
                ),
            )

    def require_market_data_allowed(self, *, operation: str) -> None:
        normalized_operation = _required_text(operation, field_name="operation")
        state = self.snapshot
        if state.market_data_allowed:
            return
        raise ProviderUnavailableError(
            "IBKR market-data admission is closed.",
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=(
                str(state.last_provider_code)
                if state.last_provider_code is not None
                else None
            ),
        )

    def observe_error(
        self,
        observation: IBKRErrorObservation,
        *,
        operation: str,
        economic_write_in_flight: bool = False,
    ) -> ProviderError | None:
        if not isinstance(observation, IBKRErrorObservation):
            raise IBKROperationalRuntimeError(
                "observation must be an IBKRErrorObservation."
            )
        self._last_provider_code = observation.code
        code = observation.code

        if code == 100:
            self._pacing_violation_latched = True
        elif code in {504, 507, 1300}:
            self._socket_connected = False
            self._provider_connected = False
            self._reconnect_required = True
            self._reconciliation_complete = False
            self._market_data_ready = False
        elif code in {1100, 2110}:
            self._provider_connected = False
            self._reconciliation_complete = False
            self._market_data_ready = False
        elif code == 1101:
            self._provider_connected = True
            self._reconnect_required = False
            self._reconciliation_complete = False
            self._market_data_ready = False
            self._market_data_resubscription_required = True
        elif code == 1102:
            self._provider_connected = True
            self._reconnect_required = False
            if not self._market_data_resubscription_required:
                self._market_data_ready = True
        elif code == 2103:
            self._market_data_ready = False
        elif code == 2104 and not self._market_data_resubscription_required:
            self._market_data_ready = True

        mapped = map_ibkr_provider_error(
            observation,
            operation=operation,
            economic_write_in_flight=economic_write_in_flight,
        )
        if (
            code == 1102
            and self._reconciliation_complete
            and not economic_write_in_flight
        ):
            mapped = None
        if mapped is not None and observation.code not in {
            100,
            200,
            201,
            202,
            203,
            326,
            502,
            503,
            504,
            507,
            1100,
            1101,
            1102,
            1300,
            2103,
            2104,
            2105,
            2106,
            2107,
            2108,
            2110,
            2158,
        }:
            self._fail_closed_latched = True
        return mapped

    def on_connected(self) -> None:
        was_disconnected = not self._socket_connected
        self._socket_connected = True
        self._provider_connected = True
        self._reconnect_required = False
        if was_disconnected:
            self._reconciliation_complete = False

    def on_disconnected(self) -> None:
        self._socket_connected = False
        self._provider_connected = False
        self._reconnect_required = True
        self._reconciliation_complete = False
        self._market_data_ready = False

    def on_throttle_start(self) -> None:
        self._transport_throttle_active = True

    def on_throttle_end(self) -> None:
        self._transport_throttle_active = False

    def mark_pacing_recovered(self) -> None:
        if self._transport_throttle_active:
            raise IBKROperationalRuntimeError(
                "Cannot clear pacing containment while transport throttling is active."
            )
        if not self._socket_connected:
            raise IBKROperationalRuntimeError(
                "Cannot clear pacing containment while disconnected."
            )
        self._pacing_violation_latched = False

    def mark_reconnected(self) -> None:
        self._socket_connected = True
        self._provider_connected = True
        self._reconnect_required = False
        self._reconciliation_complete = False

    def mark_reconciled(self) -> None:
        if not self._socket_connected or not self._provider_connected:
            raise IBKROperationalRuntimeError(
                "Cannot mark reconciliation complete while disconnected."
            )
        self._reconciliation_complete = True

    def fail_closed(self, *, provider_code: int | None = None) -> None:
        if provider_code is not None and (
            type(provider_code) is not int or provider_code <= 0
        ):
            raise IBKROperationalRuntimeError(
                "provider_code must be a positive int or None."
            )
        self._fail_closed_latched = True
        if provider_code is not None:
            self._last_provider_code = provider_code

    def mark_market_data_resubscribed(self) -> None:
        if not self._socket_connected or not self._provider_connected:
            raise IBKROperationalRuntimeError(
                "Cannot restore market data while disconnected."
            )
        self._market_data_resubscription_required = False
        self._market_data_ready = True


class IBKROperationalEventBridge:
    """Bind ib_async connectivity, error, and throttle events to the guard."""

    def __init__(
        self,
        *,
        guard: IBKROperationalGuard,
        clock: ClockPort,
    ) -> None:
        self._guard = guard
        self._clock = clock
        self._client: _OperationalClient | None = None

    def bind(self, client: object) -> IBKRPacingEvidence:
        if self._client is not None:
            self.unbind()
        operational = _normalize_operational_client(client)
        pacing = qualify_ib_async_pacing(operational.client)

        operational.connectedEvent.connect(self._on_connected)
        operational.disconnectedEvent.connect(self._on_disconnected)
        operational.errorEvent.connect(self._on_error)
        operational.client.throttleStart.connect(self._on_throttle_start)
        operational.client.throttleEnd.connect(self._on_throttle_end)
        self._client = operational
        return pacing

    def unbind(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        client.connectedEvent.disconnect(self._on_connected)
        client.disconnectedEvent.disconnect(self._on_disconnected)
        client.errorEvent.disconnect(self._on_error)
        client.client.throttleStart.disconnect(self._on_throttle_start)
        client.client.throttleEnd.disconnect(self._on_throttle_end)

    def _on_connected(self, *args: object) -> None:
        _ = args
        self._guard.on_connected()

    def _on_disconnected(self, *args: object) -> None:
        _ = args
        self._guard.on_disconnected()

    def _on_throttle_start(self, *args: object) -> None:
        _ = args
        self._guard.on_throttle_start()

    def _on_throttle_end(self, *args: object) -> None:
        _ = args
        self._guard.on_throttle_end()

    def _on_error(
        self,
        req_id: object,
        error_code: object,
        error_string: object,
        contract: object = None,
    ) -> None:
        _ = contract
        if type(req_id) is not int or type(error_code) is not int:
            self._guard.fail_closed()
            return
        if not isinstance(error_string, str) or not error_string.strip():
            self._guard.fail_closed(provider_code=error_code)
            return
        try:
            observation = IBKRErrorObservation(
                request_id=req_id,
                code=error_code,
                message=error_string,
                observed_at=self._clock.now(),
            )
            self._guard.observe_error(
                observation,
                operation="provider_event",
                economic_write_in_flight=False,
            )
        except Exception:
            self._guard.fail_closed(provider_code=error_code)


@dataclass(slots=True)
class IBKROperationalRuntime:
    """Bound provider-local operational containment runtime."""

    connection: IBKRPaperConnectionRuntime
    guard: IBKROperationalGuard
    bridge: IBKROperationalEventBridge
    pacing: IBKRPacingEvidence | None = None

    def bind(self) -> IBKRPacingEvidence:
        provider = self.connection.read_client()
        pacing = self.bridge.bind(provider)
        self.pacing = pacing
        return pacing

    def stop(self) -> None:
        self.bridge.unbind()


@dataclass(frozen=True, slots=True)
class IBKRReconnectRecoveryEvidence:
    """Sanitized evidence for one explicit reconnect recovery cycle."""

    socket_reconnected: bool
    reconciliation_ran: bool
    reconciliation_safe: bool
    consistency_status: ConsistencyStatus | None
    state_confidence: StateConfidence | None

    def __post_init__(self) -> None:
        for field_name in (
            "socket_reconnected",
            "reconciliation_ran",
            "reconciliation_safe",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKROperationalRuntimeError(
                    f"{field_name} must be a bool."
                )


class IBKRReconnectRecoveryRuntime:
    """Recover connectivity without replaying any economic write."""

    def __init__(
        self,
        *,
        connection: IBKRPaperConnectionRuntime,
        operations: IBKROperationalRuntime,
        reconciliation: IBKRReconnectReconciliation,
    ) -> None:
        self._connection = connection
        self._operations = operations
        self._reconciliation = reconciliation

    def recover(
        self,
        *,
        reconnect_socket: bool,
    ) -> IBKRReconnectRecoveryEvidence:
        if type(reconnect_socket) is not bool:
            raise IBKROperationalRuntimeError(
                "reconnect_socket must be a bool."
            )

        socket_reconnected = False
        if reconnect_socket:
            self._operations.bridge.unbind()
            self._connection.stop()
            startup = self._connection.start()
            if not startup.ready_for_startup:
                self._operations.guard.on_disconnected()
                return IBKRReconnectRecoveryEvidence(
                    socket_reconnected=False,
                    reconciliation_ran=False,
                    reconciliation_safe=False,
                    consistency_status=None,
                    state_confidence=None,
                )
            self._operations.guard.mark_reconnected()
            self._operations.bind()
            socket_reconnected = True
        else:
            state = self._operations.guard.snapshot
            if not state.socket_connected or not state.provider_connected:
                raise ProviderUnavailableError(
                    "IBKR provider connectivity is not restored.",
                    provider=IBKR_PROVIDER_KEY,
                    operation="reconnect_recovery",
                )

        outcome = self._reconciliation.reconnect()
        status = outcome.run.result_status
        confidence = outcome.run.confidence
        safe = (
            status is ConsistencyStatus.CONSISTENT
            and confidence is StateConfidence.HIGH
        )
        if safe:
            self._operations.guard.mark_reconciled()

        return IBKRReconnectRecoveryEvidence(
            socket_reconnected=socket_reconnected,
            reconciliation_ran=True,
            reconciliation_safe=safe,
            consistency_status=status,
            state_confidence=confidence,
        )


def qualify_ib_async_pacing(
    client: _LowLevelOperationalClient,
) -> IBKRPacingEvidence:
    """Require ib_async automatic throttling at or below the qualified rate."""

    max_requests = client.MaxRequests
    interval = client.RequestsInterval
    if type(max_requests) is not int or max_requests <= 0:
        raise ProviderProtocolError(
            "ib_async automatic request throttling must remain enabled.",
            provider=IBKR_PROVIDER_KEY,
            operation="pacing",
        )
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not isfinite(float(interval))
        or float(interval) <= 0
    ):
        raise ProviderProtocolError(
            "ib_async request-throttling interval is invalid.",
            provider=IBKR_PROVIDER_KEY,
            operation="pacing",
        )

    effective = max_requests / float(interval)
    if effective > IBKR_QUALIFIED_MAX_REQUEST_RATE_PER_SECOND:
        raise ProviderProtocolError(
            "ib_async request rate exceeds the qualified PyTradeKit ceiling.",
            provider=IBKR_PROVIDER_KEY,
            operation="pacing",
        )
    return IBKRPacingEvidence(
        max_requests=max_requests,
        requests_interval_seconds=float(interval),
        effective_rate_per_second=effective,
    )


def build_ibkr_operational_runtime(
    *,
    connection: IBKRPaperConnectionRuntime,
    reconciliation_complete: bool,
    clock: ClockPort,
) -> IBKROperationalRuntime:
    """Bind LOT-06.6 operational containment to a started PAPER session."""

    if not isinstance(connection, IBKRPaperConnectionRuntime):
        raise IBKROperationalRuntimeError(
            "connection must be an IBKRPaperConnectionRuntime."
        )
    if type(reconciliation_complete) is not bool:
        raise IBKROperationalRuntimeError(
            "reconciliation_complete must be a bool."
        )
    if connection.connection_evidence is None:
        raise ProviderUnavailableError(
            "IBKR operational runtime requires completed startup.",
            provider=IBKR_PROVIDER_KEY,
            operation="operational_runtime",
        )

    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=reconciliation_complete,
        market_data_ready=True,
    )
    bridge = IBKROperationalEventBridge(
        guard=guard,
        clock=clock,
    )
    runtime = IBKROperationalRuntime(
        connection=connection,
        guard=guard,
        bridge=bridge,
    )
    runtime.bind()
    return runtime


def _normalize_operational_client(client: object) -> _OperationalClient:
    required = (
        "client",
        "connectedEvent",
        "disconnectedEvent",
        "errorEvent",
    )
    if any(not hasattr(client, name) for name in required):
        raise ProviderProtocolError(
            "IBKR client lacks the qualified operational event surface.",
            provider=IBKR_PROVIDER_KEY,
            operation="operational_runtime",
        )
    operational = cast(_OperationalClient, client)
    low_level = operational.client
    low_required = (
        "MaxRequests",
        "RequestsInterval",
        "throttleStart",
        "throttleEnd",
    )
    if any(not hasattr(low_level, name) for name in low_required):
        raise ProviderProtocolError(
            "IBKR low-level client lacks qualified pacing evidence.",
            provider=IBKR_PROVIDER_KEY,
            operation="operational_runtime",
        )
    return operational


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKROperationalRuntimeError(
            f"{field_name} must be a string."
        )
    normalized = value.strip()
    if not normalized:
        raise IBKROperationalRuntimeError(
            f"{field_name} must be non-empty."
        )
    return normalized
