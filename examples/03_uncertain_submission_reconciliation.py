"""PyTradeKit 0.2 uncertain-submission reconciliation demonstration."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.execution import ExecutionStatus
from pytradekit.orders import OrderSide, OrderType, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import (
    HandleExecutionReport,
    SubmitOrder,
    SubmitOrderCommand,
)
from pytradekit.shared import CorrelationId, InstrumentId, Quantity
from pytradekit.testing import FakeClock


def main() -> None:
    """Show timeout -> uncertainty -> query -> safe convergence."""
    clock = FakeClock.at(datetime(2026, 10, 21, 20, 0, tzinfo=UTC))
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.submit_timeout(
            resolve_as=ExecutionStatus.ACCEPTED,
        ),
        clock=clock,
    )
    submit = SubmitOrder(repository=repository, execution=execution, clock=clock)
    handle = HandleExecutionReport(repository=repository)

    result = submit.execute(
        SubmitOrderCommand(
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("1")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
        )
    )
    submission_status = result.submission_status
    if submission_status is None:
        raise RuntimeError("Expected an execution submission attempt.")

    print(f"submission result: {submission_status.value}")
    print(f"order status: {result.order.status.value}")
    print(f"certainty: {result.order.execution_certainty.value}")

    aggregate = repository.get(result.order.order_id)
    if aggregate is None:
        raise RuntimeError("Expected submitted order in repository.")

    report = execution.query_order(aggregate)
    if report is None:
        raise RuntimeError("Expected fake broker reconciliation report.")

    reconciled = handle.execute(report)
    print(f"reconciled status: {reconciled.status.value}")
    print(f"reconciled certainty: {reconciled.execution_certainty.value}")


if __name__ == "__main__":
    main()
