"""End-to-end qualification of the milestone 0.2 OMS flows."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.orders import OrderSide, OrderStatus, OrderType, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import (
    CancelOrder,
    CancelOrderCommand,
    GetOrder,
    HandleExecutionReport,
    SubmitOrder,
    SubmitOrderCommand,
)
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Price, Quantity
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
USD = Currency("USD")
PRICE = Price(Decimal("101.25"), USD)


def _command(*, order_type: OrderType = OrderType.MARKET) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Quantity(Decimal("10")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        limit_price=PRICE if order_type is OrderType.LIMIT else None,
    )


def test_market_order_partial_fill_then_full_fill() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.partial_then_fill(
            price=PRICE,
            partial_quantities=(
                Quantity(Decimal("2")),
                Quantity(Decimal("3")),
            ),
        ),
        clock=clock,
    )
    submit = SubmitOrder(repository=repository, execution=execution, clock=clock)
    handle = HandleExecutionReport(repository=repository)
    get_order = GetOrder(repository=repository)

    submitted = submit.execute(_command())
    assert submitted.order.status is OrderStatus.ACCEPTED

    for report in execution.drain_reports(submitted.order.order_id):
        handle.execute(report)

    final = get_order.execute(submitted.order.order_id)
    assert final is not None
    assert final.status is OrderStatus.FILLED
    assert final.filled_quantity == Quantity(Decimal("10"))
    assert final.remaining_quantity == Quantity(Decimal("0"))


def test_limit_order_can_be_cancelled_after_acceptance() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    submit = SubmitOrder(repository=repository, execution=execution, clock=clock)
    handle = HandleExecutionReport(repository=repository)
    cancel = CancelOrder(repository=repository, execution=execution, clock=clock)
    get_order = GetOrder(repository=repository)

    submitted = submit.execute(_command(order_type=OrderType.LIMIT))
    for report in execution.drain_reports(submitted.order.order_id):
        handle.execute(report)

    cancellation = cancel.execute(CancelOrderCommand(order_id=submitted.order.order_id))
    assert cancellation.order.status is OrderStatus.CANCEL_REQUESTED

    for report in execution.drain_reports(submitted.order.order_id):
        handle.execute(report)

    final = get_order.execute(submitted.order.order_id)
    assert final is not None
    assert final.status is OrderStatus.CANCELLED
    assert final.limit_price == PRICE
