"""Fill repository port."""

from typing import Protocol

from pytradekit.execution.domain import Fill, FillId
from pytradekit.orders.domain import OrderId


class FillRepository(Protocol):
    """Persistence boundary for immutable execution fills."""

    def get(self, fill_id: FillId) -> Fill | None:
        """Return one fill by canonical identity."""
        ...

    def add(self, fill: Fill) -> None:
        """Persist one immutable fill."""
        ...

    def list_for_order(self, order_id: OrderId) -> tuple[Fill, ...]:
        """Return fills for one order in stable occurrence order."""
        ...

    def contains_external(self, external_fill_id: str) -> bool:
        """Return whether an external fill identity was already persisted."""
        ...
