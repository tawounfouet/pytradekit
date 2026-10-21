"""Order aggregate repository port."""

from typing import Protocol

from pytradekit.orders.domain import Order, OrderId


class OrderRepository(Protocol):
    """Persistence boundary for Order aggregates."""

    def get(self, order_id: OrderId) -> Order | None:
        """Return one order or None when it does not exist."""
        ...

    def add(self, order: Order) -> None:
        """Add a new aggregate."""
        ...

    def save(self, order: Order) -> None:
        """Persist changes to an existing aggregate."""
        ...
