"""Deterministic in-memory implementation of the OrderRepository port."""

from copy import deepcopy

from pytradekit.orders.domain import (
    Order,
    OrderAlreadyExistsError,
    OrderId,
    OrderNotFoundError,
)


class InMemoryOrderRepository:
    """In-memory aggregate store used by tests and milestone 0.2 flows."""

    def __init__(self) -> None:
        self._orders: dict[OrderId, Order] = {}

    def get(self, order_id: OrderId) -> Order | None:
        """Return a detached copy of an aggregate when present."""
        order = self._orders.get(order_id)
        return deepcopy(order) if order is not None else None

    def add(self, order: Order) -> None:
        """Add a new aggregate and reject duplicate identities."""
        if order.id in self._orders:
            raise OrderAlreadyExistsError(f"Order {order.id} already exists.")
        self._orders[order.id] = deepcopy(order)

    def save(self, order: Order) -> None:
        """Replace the stored aggregate while preserving its identity and version."""
        if order.id not in self._orders:
            raise OrderNotFoundError(f"Order {order.id} was not found.")
        self._orders[order.id] = deepcopy(order)

    def clear(self) -> None:
        """Remove all stored orders."""
        self._orders.clear()
