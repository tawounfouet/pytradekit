"""Domain events emitted by the Order aggregate."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.orders.domain.order_id import OrderId
from pytradekit.orders.domain.order_status import OrderStatus
from pytradekit.shared import DomainEvent, Quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCreated(DomainEvent):
    """An order was created."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderValidated(DomainEvent):
    """An order passed canonical validation."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderSubmitted(DomainEvent):
    """An order submission attempt was issued."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderAccepted(DomainEvent):
    """An order was accepted by the execution boundary."""

    order_id: OrderId
    external_order_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPartiallyFilled(DomainEvent):
    """An order received a partial fill."""

    order_id: OrderId
    fill_id: str
    filled_quantity: Quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderFilled(DomainEvent):
    """An order became fully filled."""

    order_id: OrderId
    fill_id: str
    filled_quantity: Quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderRejected(DomainEvent):
    """An order was rejected with a known reason."""

    order_id: OrderId
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCancelRequested(DomainEvent):
    """Cancellation was requested for an order."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCancelled(DomainEvent):
    """Cancellation was confirmed for an order."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCancelRejected(DomainEvent):
    """A cancellation request was rejected."""

    order_id: OrderId
    reason: str
    restored_status: OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderExpired(DomainEvent):
    """An order expired."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderFailed(DomainEvent):
    """An order entered a known failed state."""

    order_id: OrderId
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderSubmissionUncertain(DomainEvent):
    """The result of order submission became uncertain."""

    order_id: OrderId


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCancelUncertain(DomainEvent):
    """The result of a cancellation request became uncertain."""

    order_id: OrderId
