"""PyTradeKit 0.2 cancel-fill race demonstration."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.execution import ExecutionReport, ExecutionStatus, Fill, FillId
from pytradekit.orders import OrderSide, OrderType, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import (
    CancelOrder,
    CancelOrderCommand,
    GetOrder,
    HandleExecutionReport,
    SubmitOrder,
    SubmitOrderCommand,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Price, Quantity
from pytradekit.testing import (
    ExplicitTestOrderAuthorizationGate,
    ExplicitTestOrderSafetyGate,
    FakeClock,
)


def main() -> None:
    """Show that a real full fill wins over a later cancel confirmation."""
    now = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
    clock = FakeClock.at(now)
    repository = InMemoryOrderRepository()
    account_id = AccountId.new()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    authorization = ExplicitTestOrderAuthorizationGate()
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=authorization,
        safety_gate=ExplicitTestOrderSafetyGate(),
    )
    cancel = CancelOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=authorization,
        safety_gate=ExplicitTestOrderSafetyGate(),
    )
    handle = HandleExecutionReport(repository=repository)
    get_order = GetOrder(repository=repository)

    submitted = submit.execute(
        SubmitOrderCommand(
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("5")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            account_id=account_id,
        )
    )
    execution.drain_reports(submitted.order.order_id)

    cancellation = cancel.execute(
        CancelOrderCommand(
            order_id=submitted.order.order_id,
            account_id=account_id,
        )
    )
    cancel_reports = execution.drain_reports(submitted.order.order_id)
    print(f"after cancel request: {cancellation.order.status.value}")

    fill = Fill(
        id=FillId.new(),
        order_id=submitted.order.order_id,
        quantity=Quantity(Decimal("5")),
        price=Price(Decimal("100"), Currency("USD")),
        occurred_at=now,
        external_fill_id="example-race-fill",
    )
    handle.execute(
        ExecutionReport(
            order_id=submitted.order.order_id,
            status=ExecutionStatus.FILLED,
            occurred_at=now,
            correlation_id=CorrelationId.new(),
            external_order_id=submitted.order.external_order_id,
            fill=fill,
        )
    )

    for report in cancel_reports:
        handle.execute(report)

    final = get_order.execute(submitted.order.order_id)
    if final is None:
        raise RuntimeError("Expected order to remain available in the repository.")

    print(f"final status: {final.status.value}")
    print(f"final filled quantity: {final.filled_quantity}")


if __name__ == "__main__":
    main()
