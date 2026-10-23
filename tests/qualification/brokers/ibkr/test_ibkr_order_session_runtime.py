"""Qualification tests for IBKR LOT-06.4 order-session sequencing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pytradekit.brokers import ProviderExecutionContext
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRPaperConnectionRuntime,
    IBKRPaperRuntimeProfile,
    IBKRPermanentOrderId,
    IBKRTransportConnectionEvidence,
    build_ibkr_order_session_runtime,
)
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency

_NOW = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


class _LowLevel:
    def __init__(self) -> None:
        self.next_id = 500

    def isReady(self) -> bool:
        return True

    def getReqId(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


class _ProviderClient:
    def __init__(self) -> None:
        self.client = _LowLevel()


class _Transport:
    def __init__(self) -> None:
        self.client = _ProviderClient()
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
        return self.client


@dataclass
class _Order:
    orderId: int
    clientId: int
    permId: int
    orderRef: str


@dataclass
class _Status:
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


def test_lot06_4_qualifies_prewrite_sequence_and_callback_binding() -> None:
    connection = IBKRPaperConnectionRuntime(
        profile=IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(7),
        ),
        transport=_Transport(),
    )
    startup = connection.start()
    assert startup.ready_for_startup

    runtime = build_ibkr_order_session_runtime(connection=connection)
    context = ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference="ptk-lot06-4",
        quote_currency=Currency("USD"),
    )
    reservation = runtime.reserve(context)

    assert reservation.session_order_id.value == 500
    assert reservation.client_id == IBKRClientId(7)

    trade = _Trade(
        order=_Order(
            orderId=500,
            clientId=7,
            permId=9001,
            orderRef="ptk-lot06-4",
        ),
        orderStatus=_Status(
            orderId=500,
            status="Submitted",
            filled=0,
            remaining=1,
            avgFillPrice=0,
            permId=9001,
            clientId=7,
            lastFillPrice=0,
            whyHeld="",
        ),
    )
    correlated = runtime.callbacks.correlate_open_order(
        trade,
        observed_at=_NOW,
    )

    assert correlated is not None
    assert correlated.reservation.context.order_id == context.order_id
    assert (
        correlated.observation.permanent_order_id
        == IBKRPermanentOrderId(9001)
    )

    identity = runtime.identities.find_by_permanent_order_id(
        IBKRPermanentOrderId(9001)
    )
    assert identity is not None
    assert identity.client_reference.value == "ptk-lot06-4"

    connection.stop()
