"""Alpaca reconciliation activity adapter tests."""

from pytradekit.brokers.adapters.alpaca.reconciliation import AlpacaExternalActivityReader
from pytradekit.orders.domain import OrderId


class FakeActivityClient:
    def get(self, path: str, data: dict[str, object] | None = None) -> object:
        assert path == "/account/activities/FILL"
        assert data is not None
        return [
            {
                "id": "activity-1",
                "order_id": "provider-order-1",
                "qty": "2",
                "price": "123.45",
                "transaction_time": "2026-10-22T12:00:00+00:00",
            }
        ]


class KnownOrders:
    def __init__(self, order_id: OrderId) -> None:
        self._order_id = order_id

    def resolve_order_id(self, external_order_id: str) -> OrderId | None:
        assert external_order_id == "provider-order-1"
        return self._order_id


def test_alpaca_fill_activity_preserves_stable_execution_identity() -> None:
    order_id = OrderId.new()
    fills = AlpacaExternalActivityReader(
        client=FakeActivityClient(),
        orders=KnownOrders(order_id),
    ).list_fills()

    assert len(fills) == 1
    assert fills[0].external_fill_id == "activity-1"
    assert fills[0].order_id == order_id
    assert fills[0].origin.value == "INTERNAL"
