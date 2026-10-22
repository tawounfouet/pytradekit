"""Mapping between Order domain aggregates and PostgreSQL rows."""

from pytradekit.orders.adapters.postgres.models import OrderModel
from pytradekit.orders.domain import (
    ExecutionCertainty,
    Order,
    OrderId,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from pytradekit.persistence import PersistenceError
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Price, Quantity


def order_to_values(order: Order) -> dict[str, object]:
    """Return database values for one Order aggregate."""
    return {
        "id": order.id.value,
        "instrument_id": order.instrument_id.value,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "quantity": order.quantity.value,
        "time_in_force": order.time_in_force.value,
        "status": order.status.value,
        "filled_quantity": order.filled_quantity.value,
        "limit_price_value": order.limit_price.value if order.limit_price is not None else None,
        "limit_price_currency": (
            order.limit_price.currency.code if order.limit_price is not None else None
        ),
        "client_order_id": order.client_order_id,
        "external_order_id": order.external_order_id,
        "execution_certainty": order.execution_certainty.value,
        "rejection_reason": order.rejection_reason,
        "failure_reason": order.failure_reason,
        "version": order.version,
        "cancel_requested": order.cancel_requested,
        "cancel_previous_status": (
            order._cancel_previous_status.value
            if order._cancel_previous_status is not None
            else None
        ),
        "processed_fill_ids": sorted(order._processed_fill_ids),
        "correlation_id": order.correlation_id.value,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def order_from_model(model: OrderModel) -> Order:
    """Rebuild a lossless detached Order aggregate."""
    limit_price: Price | None = None
    if model.limit_price_value is not None or model.limit_price_currency is not None:
        if model.limit_price_value is None or model.limit_price_currency is None:
            raise PersistenceError("Stored limit price is incomplete.")
        limit_price = Price(model.limit_price_value, Currency(model.limit_price_currency))

    return Order(
        id=OrderId(model.id),
        instrument_id=InstrumentId(model.instrument_id),
        side=OrderSide(model.side),
        order_type=OrderType(model.order_type),
        quantity=Quantity(model.quantity),
        time_in_force=TimeInForce(model.time_in_force),
        status=OrderStatus(model.status),
        filled_quantity=Quantity(model.filled_quantity),
        limit_price=limit_price,
        client_order_id=model.client_order_id,
        external_order_id=model.external_order_id,
        execution_certainty=ExecutionCertainty(model.execution_certainty),
        rejection_reason=model.rejection_reason,
        failure_reason=model.failure_reason,
        version=model.version,
        cancel_requested=model.cancel_requested,
        created_at=model.created_at,
        updated_at=model.updated_at,
        correlation_id=CorrelationId(model.correlation_id),
        _cancel_previous_status=(
            OrderStatus(model.cancel_previous_status)
            if model.cancel_previous_status is not None
            else None
        ),
        _processed_fill_ids=set(model.processed_fill_ids),
        _domain_events=[],
    )
