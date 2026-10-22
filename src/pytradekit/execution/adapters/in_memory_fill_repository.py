"""In-memory FillRepository implementation."""

from copy import deepcopy

from pytradekit.execution.domain import Fill, FillId
from pytradekit.orders.domain import OrderId
from pytradekit.persistence import DuplicatePersistenceRecordError


class InMemoryFillRepository:
    """Deterministic immutable fill store."""

    def __init__(self) -> None:
        self._fills: dict[FillId, Fill] = {}
        self._external_ids: set[str] = set()

    def get(self, fill_id: FillId) -> Fill | None:
        fill = self._fills.get(fill_id)
        return deepcopy(fill) if fill is not None else None

    def add(self, fill: Fill) -> None:
        if fill.id in self._fills:
            raise DuplicatePersistenceRecordError(f"Fill {fill.id} already exists.")
        if fill.external_fill_id is not None and fill.external_fill_id in self._external_ids:
            raise DuplicatePersistenceRecordError(
                f"External fill {fill.external_fill_id} already exists."
            )
        self._fills[fill.id] = deepcopy(fill)
        if fill.external_fill_id is not None:
            self._external_ids.add(fill.external_fill_id)

    def list_for_order(self, order_id: OrderId) -> tuple[Fill, ...]:
        fills = [
            deepcopy(fill)
            for fill in self._fills.values()
            if fill.order_id == order_id
        ]
        return tuple(sorted(fills, key=lambda item: (item.occurred_at, str(item.id))))

    def contains_external(self, external_fill_id: str) -> bool:
        if not isinstance(external_fill_id, str) or not external_fill_id.strip():
            raise ValueError("External fill id must be a non-empty string.")
        return external_fill_id.strip() in self._external_ids
