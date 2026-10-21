"""Commands, DTOs, and application results for Orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.execution import CancelStatus, SubmissionStatus
from pytradekit.orders.domain import (
    ExecutionCertainty,
    Order,
    OrderId,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from pytradekit.shared import CorrelationId, InstrumentId, Price, Quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class SubmitOrderCommand:
    """Application command for a canonical order submission."""

    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    time_in_force: TimeInForce
    correlation_id: CorrelationId
    limit_price: Price | None = None
    client_order_id: str | None = None
    order_id: OrderId | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelOrderCommand:
    """Application command for cancelling an existing order."""

    order_id: OrderId


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    """Immutable read DTO for the public application boundary."""

    order_id: OrderId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    filled_quantity: Quantity
    remaining_quantity: Quantity
    status: OrderStatus
    time_in_force: TimeInForce
    limit_price: Price | None
    client_order_id: str | None
    external_order_id: str | None
    execution_certainty: ExecutionCertainty
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_order(cls, order: Order) -> OrderSnapshot:
        """Map an aggregate to its stable read representation."""
        return cls(
            order_id=order.id,
            instrument_id=order.instrument_id,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            remaining_quantity=order.remaining_quantity,
            status=order.status,
            time_in_force=order.time_in_force,
            limit_price=order.limit_price,
            client_order_id=order.client_order_id,
            external_order_id=order.external_order_id,
            execution_certainty=order.execution_certainty,
            created_at=order.created_at,
            updated_at=order.updated_at,
            version=order.version,
        )


@dataclass(frozen=True, slots=True)
class SubmitOrderResult:
    """Result returned by SubmitOrder."""

    order: OrderSnapshot
    submission_status: SubmissionStatus


@dataclass(frozen=True, slots=True)
class CancelOrderResult:
    """Result returned by CancelOrder."""

    order: OrderSnapshot
    cancel_status: CancelStatus
