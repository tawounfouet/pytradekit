"""Deterministic in-memory implementation of the OrderRepository port."""

from copy import deepcopy

from pytradekit.orders.domain import (
    ExecutionCertainty,
    Order,
    OrderAlreadyExistsError,
    OrderId,
    OrderNotFoundError,
)
from pytradekit.orders.domain.transitions import TERMINAL_ORDER_STATUSES


class InMemoryOrderRepository:
    """In-memory aggregate store used by tests and milestone flows."""

    def __init__(self) -> None:
        self._orders: dict[OrderId, Order] = {}

    def get(self, order_id: OrderId) -> Order | None:
        """Return a detached copy of an aggregate when present."""

        order = self._orders.get(order_id)
        return deepcopy(order) if order is not None else None

    def get_by_client_order_id(self, client_order_id: str) -> Order | None:
        """Return one order by its stable client reference."""

        normalized = client_order_id.strip()
        for order in self._orders.values():
            if order.client_order_id == normalized:
                return deepcopy(order)
        return None

    def get_by_external_order_id(self, external_order_id: str) -> Order | None:
        """Return one order by provider order identity."""

        normalized = external_order_id.strip()
        for order in self._orders.values():
            if order.external_order_id == normalized:
                return deepcopy(order)
        return None

    def list_reconcilable(self) -> tuple[Order, ...]:
        """Return non-terminal or explicitly uncertain orders in stable order."""

        orders = [
            order
            for order in self._orders.values()
            if order.status not in TERMINAL_ORDER_STATUSES
            or order.execution_certainty is ExecutionCertainty.UNCERTAIN
        ]
        orders.sort(key=lambda order: (order.created_at, str(order.id)))
        return tuple(deepcopy(order) for order in orders)

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
