"""Unit tests for the Alpaca PAPER ExecutionPort adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, OrderRequest

from pytradekit.brokers import ProviderStateReconciliationRequired
from pytradekit.brokers.adapters.alpaca.execution import (
    AlpacaCommandClient,
    AlpacaExecutionAdapter,
    AlpacaInstrumentResolver,
    AlpacaReadClient,
)
from pytradekit.execution import CancelStatus, SubmissionStatus
from pytradekit.orders.domain import (
    Order,
    OrderId,
    OrderSide,
    OrderType,
    TimeInForce,
)
from pytradekit.orders.ports import ExecutionPort
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Price,
    Quantity,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
PROVIDER_ORDER_ID = UUID("11111111-2222-3333-4444-555555555555")


class _CommandClient:
    def __init__(
        self,
        *,
        submit_response: object | None = None,
        submit_error: Exception | None = None,
        cancel_error: Exception | None = None,
    ) -> None:
        self.submit_response = submit_response
        self.submit_error = submit_error
        self.cancel_error = cancel_error
        self.submitted: list[OrderRequest] = []
        self.cancelled: list[UUID | str] = []

    def submit_order(self, order_data: OrderRequest) -> object:
        self.submitted.append(order_data)
        if self.submit_error is not None:
            raise self.submit_error
        if self.submit_response is None:
            raise AssertionError("Test submit response was not configured.")
        return self.submit_response

    def cancel_order_by_id(self, order_id: UUID | str) -> None:
        self.cancelled.append(order_id)
        if self.cancel_error is not None:
            raise self.cancel_error


class _ReadClient:
    def __init__(
        self,
        *,
        by_id: object | None = None,
        by_client_id: object | None = None,
        by_id_error: Exception | None = None,
        by_client_error: Exception | None = None,
    ) -> None:
        self.by_id = by_id
        self.by_client_id = by_client_id
        self.by_id_error = by_id_error
        self.by_client_error = by_client_error
        self.id_queries: list[UUID | str] = []
        self.client_queries: list[str] = []

    def get_order_by_id(self, order_id: UUID | str) -> object:
        self.id_queries.append(order_id)
        if self.by_id_error is not None:
            raise self.by_id_error
        if self.by_id is None:
            raise AssertionError("Test order-by-id response was not configured.")
        return self.by_id

    def get_order_by_client_id(self, client_id: str) -> object:
        self.client_queries.append(client_id)
        if self.by_client_error is not None:
            raise self.by_client_error
        if self.by_client_id is None:
            raise AssertionError("Test order-by-client-id response was not configured.")
        return self.by_client_id


class _Resolver:
    def __init__(self, mapping: InstrumentMapping | None) -> None:
        self.mapping = mapping

    def resolve(self, instrument_id: InstrumentId) -> InstrumentMapping | None:
        if self.mapping is None:
            return None
        if self.mapping.instrument_id != instrument_id:
            return None
        return self.mapping


def _mapping(instrument_id: InstrumentId) -> InstrumentMapping:
    return InstrumentMapping(
        instrument_id=instrument_id,
        provider="alpaca",
        external_symbol="AAPL",
        external_id="asset-aapl",
    )


def _order(
    *,
    order_type: OrderType = OrderType.MARKET,
    tif: TimeInForce = TimeInForce.DAY,
    limit_price: Decimal | None = None,
) -> Order:
    instrument_id = InstrumentId.new()
    order_id = OrderId.new()
    correlation_id = CorrelationId.new()
    quantity = Quantity(Decimal("1.25"))

    if order_type is OrderType.MARKET:
        order = Order.create_market(
            order_id=order_id,
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            quantity=quantity,
            time_in_force=tif,
            correlation_id=correlation_id,
            occurred_at=NOW,
            client_order_id="ptk-order-123",
        )
    else:
        order = Order.create_limit(
            order_id=order_id,
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            quantity=quantity,
            time_in_force=tif,
            correlation_id=correlation_id,
            occurred_at=NOW,
            limit_price=Price(limit_price or Decimal("191.25"), Currency("USD")),
            client_order_id="ptk-order-123",
        )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    return order


def _alpaca_order(
    order: Order,
    *,
    status: AlpacaOrderStatus = AlpacaOrderStatus.NEW,
    filled_qty: str = "0",
    filled_avg_price: str | None = None,
) -> AlpacaOrder:
    return AlpacaOrder.model_construct(
        id=PROVIDER_ORDER_ID,
        client_order_id=order.client_order_id,
        status=status,
        updated_at=NOW,
        canceled_at=None,
        expired_at=None,
        filled_qty=filled_qty,
        filled_avg_price=filled_avg_price,
    )


def _adapter(
    order: Order,
    *,
    command: _CommandClient,
    read: _ReadClient | None = None,
) -> AlpacaExecutionAdapter:
    return AlpacaExecutionAdapter(
        command_client=cast(AlpacaCommandClient, command),
        read_client=cast(AlpacaReadClient, read or _ReadClient()),
        instruments=cast(AlpacaInstrumentResolver, _Resolver(_mapping(order.instrument_id))),
    )


def _api_error(status: int, *, code: int = 40010001, message: str = "provider error") -> APIError:
    http_error = SimpleNamespace(
        response=SimpleNamespace(status_code=status),
        request=None,
    )
    return APIError(  # type: ignore[no-untyped-call]
        f'{{"code": {code}, "message": "{message}"}}',
        http_error=http_error,
    )


def test_adapter_structurally_satisfies_execution_port() -> None:
    order = _order()
    adapter: ExecutionPort = _adapter(
        order,
        command=_CommandClient(submit_response=_alpaca_order(order)),
    )

    assert isinstance(adapter, AlpacaExecutionAdapter)


def test_market_submit_maps_canonical_order_and_submits_once() -> None:
    order = _order()
    command = _CommandClient(submit_response=_alpaca_order(order))
    adapter = _adapter(order, command=command)

    result = adapter.submit(order)

    assert result.status is SubmissionStatus.ACKNOWLEDGED
    assert result.external_order_id == str(PROVIDER_ORDER_ID)
    assert len(command.submitted) == 1
    request = command.submitted[0]
    assert isinstance(request, MarketOrderRequest)
    assert request.symbol == "AAPL"
    assert request.qty == 1.25
    assert request.side is not None
    assert request.side.value == "buy"
    assert request.time_in_force.value == "day"
    assert request.client_order_id == "ptk-order-123"


def test_limit_submit_maps_limit_price_and_submits_once() -> None:
    order = _order(order_type=OrderType.LIMIT, limit_price=Decimal("191.25"))
    command = _CommandClient(submit_response=_alpaca_order(order))
    adapter = _adapter(order, command=command)

    result = adapter.submit(order)

    assert result.status is SubmissionStatus.ACKNOWLEDGED
    assert len(command.submitted) == 1
    request = command.submitted[0]
    assert isinstance(request, LimitOrderRequest)
    assert request.limit_price == 191.25


def test_submit_rejects_tif_outside_frozen_contract_without_network_call() -> None:
    order = _order(tif=TimeInForce.GTC)
    command = _CommandClient(submit_response=_alpaca_order(order))
    adapter = _adapter(order, command=command)

    result = adapter.submit(order)

    assert result.status is SubmissionStatus.REJECTED
    assert command.submitted == []


def test_provider_422_becomes_known_submission_rejection() -> None:
    order = _order()
    command = _CommandClient(submit_error=_api_error(422))
    adapter = _adapter(order, command=command)

    result = adapter.submit(order)

    assert result.status is SubmissionStatus.REJECTED
    assert len(command.submitted) == 1


def test_provider_504_becomes_uncertain_without_second_submit() -> None:
    order = _order()
    command = _CommandClient(submit_error=_api_error(504))
    adapter = _adapter(order, command=command)

    result = adapter.submit(order)

    assert result.status is SubmissionStatus.UNCERTAIN
    assert len(command.submitted) == 1


def test_cancel_uses_known_external_id_exactly_once() -> None:
    order = _order()
    order.external_order_id = str(PROVIDER_ORDER_ID)
    command = _CommandClient(submit_response=_alpaca_order(order))
    adapter = _adapter(order, command=command)

    result = adapter.cancel(order)

    assert result.status is CancelStatus.ACKNOWLEDGED
    assert command.cancelled == [PROVIDER_ORDER_ID]


def test_cancel_recovers_external_id_by_client_reference_before_single_cancel() -> None:
    order = _order()
    provider_order = _alpaca_order(order)
    command = _CommandClient(submit_response=provider_order)
    read = _ReadClient(by_client_id=provider_order)
    adapter = _adapter(order, command=command, read=read)

    result = adapter.cancel(order)

    assert result.status is CancelStatus.ACKNOWLEDGED
    assert read.client_queries == ["ptk-order-123"]
    assert command.cancelled == [PROVIDER_ORDER_ID]


def test_cancel_504_becomes_uncertain_without_second_cancel() -> None:
    order = _order()
    order.external_order_id = str(PROVIDER_ORDER_ID)
    command = _CommandClient(
        submit_response=_alpaca_order(order),
        cancel_error=_api_error(504),
    )
    adapter = _adapter(order, command=command)

    result = adapter.cancel(order)

    assert result.status is CancelStatus.UNCERTAIN
    assert command.cancelled == [PROVIDER_ORDER_ID]


def test_query_uses_external_order_id_when_available() -> None:
    order = _order()
    order.external_order_id = str(PROVIDER_ORDER_ID)
    provider_order = _alpaca_order(order, status=AlpacaOrderStatus.NEW)
    read = _ReadClient(by_id=provider_order)
    adapter = _adapter(
        order,
        command=_CommandClient(submit_response=provider_order),
        read=read,
    )

    report = adapter.query_order(order)

    assert report is not None
    assert report.status.value == "accepted"
    assert read.id_queries == [PROVIDER_ORDER_ID]
    assert read.client_queries == []


def test_query_uses_client_reference_when_external_id_is_unknown() -> None:
    order = _order()
    provider_order = _alpaca_order(order, status=AlpacaOrderStatus.NEW)
    read = _ReadClient(by_client_id=provider_order)
    adapter = _adapter(
        order,
        command=_CommandClient(submit_response=provider_order),
        read=read,
    )

    report = adapter.query_order(order)

    assert report is not None
    assert report.external_order_id == str(PROVIDER_ORDER_ID)
    assert read.client_queries == ["ptk-order-123"]


def test_query_404_returns_none_without_resubmit() -> None:
    order = _order()
    command = _CommandClient(submit_response=_alpaca_order(order))
    read = _ReadClient(by_client_error=_api_error(404))
    adapter = _adapter(order, command=command, read=read)

    report = adapter.query_order(order)

    assert report is None
    assert command.submitted == []
    assert read.client_queries == ["ptk-order-123"]


def test_filled_snapshot_requires_reconciliation_and_does_not_fabricate_fill() -> None:
    order = _order()
    provider_order = _alpaca_order(
        order,
        status=AlpacaOrderStatus.FILLED,
        filled_qty="1.25",
        filled_avg_price="191.25",
    )
    read = _ReadClient(by_client_id=provider_order)
    adapter = _adapter(
        order,
        command=_CommandClient(submit_response=provider_order),
        read=read,
    )

    with pytest.raises(ProviderStateReconciliationRequired):
        adapter.query_order(order)


def test_precision_loss_is_rejected_before_network_submit() -> None:
    order = _order()
    order.quantity = Quantity(Decimal("0.123456789123456789123456789"))
    command = _CommandClient(submit_response=_alpaca_order(order))
    adapter = _adapter(order, command=command)

    with pytest.raises(Exception, match="represented safely"):
        adapter.submit(order)

    assert command.submitted == []