"""Unit tests for IBKR LOT-06.4 order session sequencing and callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderUnavailableError,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRCallbackCorrelationRouter,
    IBKRClientId,
    IBKRCorrelatedOpenOrder,
    IBKRCorrelatedOrderError,
    IBKRCorrelatedOrderStatus,
    IBKROrderCorrelationRegistry,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKROrderSessionRuntime,
    IBKRPaperConnectionRuntime,
    IBKRPaperRuntimeProfile,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
    IBKRTransportConnectionEvidence,
    build_ibkr_order_session_runtime,
)
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency

_NOW = datetime(2026, 10, 23, 9, 30, tzinfo=UTC)


class _LowLevel:
    def __init__(self, ids: list[int]) -> None:
        self.ids = list(ids)
        self.ready = True
        self.calls = 0

    def isReady(self) -> bool:
        return self.ready

    def getReqId(self) -> int:
        self.calls += 1
        if not self.ids:
            raise RuntimeError("no ids")
        return self.ids.pop(0)


class _ProviderClient:
    def __init__(self, low_level: _LowLevel) -> None:
        self.client = low_level


class _Transport:
    def __init__(self, provider_client: _ProviderClient) -> None:
        self.provider_client = provider_client
        self.connected = False

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
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
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def read_client(self) -> object:
        if not self.connected:
            raise RuntimeError("disconnected")
        return self.provider_client


@dataclass
class _Order:
    orderId: int
    clientId: int
    permId: int
    orderRef: str


@dataclass
class _OrderStatus:
    orderId: int
    status: str
    filled: object
    remaining: object
    avgFillPrice: object
    permId: int
    clientId: int
    lastFillPrice: object
    whyHeld: str


@dataclass
class _Trade:
    order: object
    orderStatus: object
    advancedError: str = ""


def _context(
    *,
    reference: str = "ptk-session-1",
    order_id: OrderId | None = None,
) -> ProviderExecutionContext:
    return ProviderExecutionContext(
        order_id=order_id or OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference=reference,
        quote_currency=Currency("USD"),
    )


def _runtime(
    ids: list[int] | None = None,
) -> tuple[IBKROrderSessionRuntime, _LowLevel, _Transport]:
    low_level = _LowLevel(ids or [100, 101, 102])
    transport = _Transport(_ProviderClient(low_level))
    connection = IBKRPaperConnectionRuntime(
        profile=IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(7),
        ),
        transport=transport,
    )
    startup = connection.start()
    assert startup.ready_for_startup
    return build_ibkr_order_session_runtime(
        connection=connection
    ), low_level, transport


def _trade(
    *,
    order_id: int = 100,
    client_id: int = 7,
    perm_id: int = 700,
    order_ref: str = "ptk-session-1",
    status: str = "Submitted",
    filled: object = 0,
    remaining: object = 10,
    average_fill_price: object = 0,
    last_fill_price: object = 0,
) -> _Trade:
    return _Trade(
        order=_Order(
            orderId=order_id,
            clientId=client_id,
            permId=perm_id,
            orderRef=order_ref,
        ),
        orderStatus=_OrderStatus(
            orderId=order_id,
            status=status,
            filled=filled,
            remaining=remaining,
            avgFillPrice=average_fill_price,
            permId=perm_id,
            clientId=client_id,
            lastFillPrice=last_fill_price,
            whyHeld="",
        ),
    )


def test_reserve_uses_synchronized_provider_sequence() -> None:
    runtime, low_level, _transport = _runtime([100, 101])

    first = runtime.reserve(_context(reference="ptk-100"))
    second = runtime.reserve(_context(reference="ptk-101"))

    assert first.client_id == IBKRClientId(7)
    assert first.session_order_id == IBKRSessionOrderId(100)
    assert first.order_reference == IBKROrderReference("ptk-100")
    assert second.session_order_id == IBKRSessionOrderId(101)
    assert runtime.sequencer.last_reserved == IBKRSessionOrderId(101)
    assert low_level.calls == 2

    identity = runtime.identities.find_by_routing_key(
        client_id=IBKRClientId(7),
        session_order_id=IBKRSessionOrderId(100),
    )
    assert identity is not None
    assert identity.client_reference == IBKROrderReference("ptk-100")
    assert identity.permanent_order_id is None
    assert len(runtime.correlations) == 2


def test_reserve_requires_started_paper_runtime() -> None:
    low_level = _LowLevel([100])
    connection = IBKRPaperConnectionRuntime(
        profile=IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(7),
        ),
        transport=_Transport(_ProviderClient(low_level)),
    )
    runtime = build_ibkr_order_session_runtime(connection=connection)

    with pytest.raises(ProviderUnavailableError, match="startup"):
        runtime.reserve(_context())


def test_reserve_requires_ready_request_sequence() -> None:
    runtime, low_level, _transport = _runtime([100])
    low_level.ready = False

    with pytest.raises(ProviderProtocolError, match="protocol-ready"):
        runtime.reserve(_context())


def test_non_monotonic_order_sequence_fails_closed() -> None:
    runtime, _low_level, _transport = _runtime([100, 100])
    runtime.reserve(_context(reference="ptk-100"))

    with pytest.raises(ProviderProtocolError, match="monotonically"):
        runtime.reserve(_context(reference="ptk-duplicate"))


def test_same_canonical_order_cannot_receive_two_reservations() -> None:
    runtime, _low_level, _transport = _runtime([100, 101])
    order_id = OrderId.new()
    runtime.reserve(
        _context(reference="ptk-first", order_id=order_id)
    )

    with pytest.raises(ProviderProtocolError, match="conflicts"):
        runtime.reserve(
            _context(reference="ptk-second", order_id=order_id)
        )


def test_open_order_callback_binds_perm_id_to_reserved_route() -> None:
    runtime, _low_level, _transport = _runtime([100])
    reservation = runtime.reserve(_context())

    correlated = runtime.callbacks.correlate_open_order(
        _trade(),
        observed_at=_NOW,
    )

    assert isinstance(correlated, IBKRCorrelatedOpenOrder)
    assert correlated.reservation == reservation
    assert correlated.observation.permanent_order_id == IBKRPermanentOrderId(700)

    identity = runtime.identities.find_by_routing_key(
        client_id=IBKRClientId(7),
        session_order_id=IBKRSessionOrderId(100),
    )
    assert identity is not None
    assert identity.permanent_order_id == IBKRPermanentOrderId(700)


def test_unknown_open_order_is_not_adopted() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())

    result = runtime.callbacks.correlate_open_order(
        _trade(order_id=999),
        observed_at=_NOW,
    )

    assert result is None
    assert len(runtime.correlations) == 1


def test_other_client_open_order_is_not_adopted() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())

    result = runtime.callbacks.correlate_open_order(
        _trade(client_id=8),
        observed_at=_NOW,
    )

    assert result is None


def test_open_order_conflicting_order_ref_fails_closed() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())

    with pytest.raises(ProviderProtocolError, match="orderRef"):
        runtime.callbacks.correlate_open_order(
            _trade(order_ref="different-ref"),
            observed_at=_NOW,
        )


def test_order_status_callback_correlates_and_binds_perm_id() -> None:
    runtime, _low_level, _transport = _runtime([100])
    reservation = runtime.reserve(_context())

    correlated = runtime.callbacks.correlate_order_status(
        _trade(
            filled=Decimal("4"),
            remaining=Decimal("6"),
            average_fill_price=Decimal("100.25"),
            last_fill_price=Decimal("100.25"),
        ),
        observed_at=_NOW,
    )

    assert isinstance(correlated, IBKRCorrelatedOrderStatus)
    assert correlated.reservation == reservation
    assert correlated.observation.filled == Decimal("4")
    assert correlated.observation.remaining == Decimal("6")
    assert (
        correlated.observation.average_fill_price
        == Decimal("100.25")
    )
    assert correlated.observation.permanent_order_id == IBKRPermanentOrderId(700)


def test_order_status_zero_prices_become_unknown() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())

    correlated = runtime.callbacks.correlate_order_status(
        _trade(),
        observed_at=_NOW,
    )

    assert correlated is not None
    assert correlated.observation.average_fill_price is None
    assert correlated.observation.last_fill_price is None


def test_order_status_conflicting_client_id_fails_closed() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())
    trade = _trade()
    assert isinstance(trade.orderStatus, _OrderStatus)
    trade.orderStatus.clientId = 8

    with pytest.raises(ProviderProtocolError, match="clientId"):
        runtime.callbacks.correlate_order_status(
            trade,
            observed_at=_NOW,
        )


def test_order_status_conflicting_perm_id_fails_closed() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())
    trade = _trade()
    assert isinstance(trade.orderStatus, _OrderStatus)
    trade.orderStatus.permId = 701

    with pytest.raises(ProviderProtocolError, match="permId"):
        runtime.callbacks.correlate_order_status(
            trade,
            observed_at=_NOW,
        )


def test_order_error_is_correlated_only_for_reserved_order_id() -> None:
    runtime, _low_level, _transport = _runtime([100])
    reservation = runtime.reserve(_context())

    correlated = runtime.callbacks.correlate_error(
        request_or_order_id=100,
        error_code=201,
        message="provider rejection",
        advanced_order_reject_json=None,
        observed_at=_NOW,
    )
    unrelated = runtime.callbacks.correlate_error(
        request_or_order_id=999,
        error_code=200,
        message="not an order callback",
        advanced_order_reject_json=None,
        observed_at=_NOW,
    )

    assert isinstance(correlated, IBKRCorrelatedOrderError)
    assert correlated.reservation == reservation
    assert correlated.observation.error_code == 201
    assert unrelated is None


def test_general_negative_error_event_is_not_classified_as_order_error() -> None:
    runtime, _low_level, _transport = _runtime([100])
    runtime.reserve(_context())

    result = runtime.callbacks.correlate_error(
        request_or_order_id=-1,
        error_code=1100,
        message="connectivity",
        advanced_order_reject_json=None,
        observed_at=_NOW,
    )

    assert result is None


def test_order_correlation_registry_rejects_reference_rebind() -> None:
    correlations = IBKROrderCorrelationRegistry()
    identities = IBKROrderIdentityRegistry()
    router = IBKRCallbackCorrelationRouter(
        expected_client_id=IBKRClientId(7),
        identities=identities,
        correlations=correlations,
    )
    first = _context(reference="same-ref")
    second = _context(reference="same-ref")
    one = correlations.register(
        reservation=__import__(
            "pytradekit.brokers.adapters.ibkr",
            fromlist=["IBKROrderSessionReservation"],
        ).IBKROrderSessionReservation(
            context=first,
            client_id=IBKRClientId(7),
            session_order_id=IBKRSessionOrderId(100),
            order_reference=IBKROrderReference("same-ref"),
        )
    )
    assert one.context == first
    assert router is not None

    with pytest.raises(Exception, match="orderRef"):
        correlations.register(
            reservation=__import__(
                "pytradekit.brokers.adapters.ibkr",
                fromlist=["IBKROrderSessionReservation"],
            ).IBKROrderSessionReservation(
                context=second,
                client_id=IBKRClientId(7),
                session_order_id=IBKRSessionOrderId(101),
                order_reference=IBKROrderReference("same-ref"),
            )
        )
