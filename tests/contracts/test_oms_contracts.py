"""Contract tests for milestone 0.2 ports and public package surfaces."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.execution import Fill
from pytradekit.orders import Order, OrderId, OrderSide, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.ports import ExecutionPort, OrderRepository
from pytradekit.shared import CorrelationId, InstrumentId, Quantity
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


def _order() -> Order:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    return order


def _accept_repository(repository: OrderRepository) -> None:
    order = _order()
    repository.add(order)
    loaded = repository.get(order.id)
    assert loaded is not None
    assert loaded.id == order.id
    assert loaded.version == order.version

    loaded.accept(external_order_id="broker-1", occurred_at=NOW)
    repository.save(loaded)
    reloaded = repository.get(order.id)
    assert reloaded is not None
    assert reloaded.version == loaded.version


def _accept_execution_port(port: ExecutionPort) -> None:
    result = port.submit(_order())
    assert result.external_order_id is not None


def test_in_memory_repository_satisfies_order_repository_contract() -> None:
    _accept_repository(InMemoryOrderRepository())


def test_fake_adapter_satisfies_execution_port_contract() -> None:
    _accept_execution_port(
        FakeExecutionAdapter(
            scenario=FakeExecutionScenario.accept_immediately(),
            clock=FakeClock.at(NOW),
        )
    )


def test_public_execution_fill_is_importable() -> None:
    assert Fill.__module__.startswith("pytradekit.execution")
