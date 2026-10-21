"""ProcessFill application use case."""

from pytradekit.execution import Fill
from pytradekit.orders.application.models import OrderSnapshot
from pytradekit.orders.domain import OrderNotFoundError
from pytradekit.orders.ports import OrderRepository


class ProcessFill:
    """Apply one fill idempotently to the authoritative Order aggregate."""

    def __init__(self, *, repository: OrderRepository) -> None:
        self._repository = repository

    def execute(
        self,
        fill: Fill,
        *,
        external_order_id: str | None = None,
    ) -> OrderSnapshot:
        """Apply a fill exactly once and return the updated order snapshot."""
        order = self._repository.get(fill.order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {fill.order_id} was not found.")

        order.apply_fill(
            fill_id=fill.deduplication_key,
            fill_quantity=fill.quantity,
            occurred_at=fill.occurred_at,
            external_order_id=external_order_id,
        )
        self._repository.save(order)
        return OrderSnapshot.from_order(order)
