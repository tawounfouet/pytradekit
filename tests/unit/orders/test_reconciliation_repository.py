"""Unit tests for reconciliation queries on the in-memory order repository."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders import ExecutionCertainty, OrderSide, OrderStatus, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.domain import Order, OrderId
from pytradekit.shared import CorrelationId, InstrumentId, Quantity

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _submitted_order() -> Order:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    return order


def test_reconciliation_queries_resolve_both_provider_identities() -> None:
    repository = InMemoryOrderRepository()
    order = _submitted_order()
    order.accept(
        external_order_id="11111111-2222-3333-4444-555555555555",
        occurred_at=NOW,
    )
    repository.add(order)

    assert repository.get_by_client_order_id(order.client_order_id or "") == order
    assert repository.get_by_external_order_id(order.external_order_id or "") == order
    assert repository.list_reconcilable() == (order,)


def test_terminal_confirmed_order_is_not_reconcilable() -> None:
    repository = InMemoryOrderRepository()
    order = _submitted_order()
    order.reject(reason="known rejection", occurred_at=NOW)
    repository.add(order)

    assert order.status is OrderStatus.REJECTED
    assert order.execution_certainty is ExecutionCertainty.CONFIRMED
    assert repository.list_reconcilable() == ()
