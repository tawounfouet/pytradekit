"""Read use cases for Orders."""

from pytradekit.orders.application.models import OrderSnapshot
from pytradekit.orders.domain import OrderId
from pytradekit.orders.ports import OrderRepository


class GetOrder:
    """Read one order without exposing the mutable aggregate."""

    def __init__(self, *, repository: OrderRepository) -> None:
        self._repository = repository

    def execute(self, order_id: OrderId) -> OrderSnapshot | None:
        """Return one order snapshot or None."""
        order = self._repository.get(order_id)
        return OrderSnapshot.from_order(order) if order is not None else None
