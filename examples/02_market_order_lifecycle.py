"""PyTradeKit 0.2 market-order lifecycle demonstration."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.orders import OrderSide, OrderType, TimeInForce
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import (
    GetOrder,
    HandleExecutionReport,
    SubmitOrder,
    SubmitOrderCommand,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Price, Quantity
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock


def main() -> None:
    """Submit a market order and process deterministic partial fills."""
    clock = FakeClock.at(datetime(2026, 10, 21, 20, 0, tzinfo=UTC))
    repository = InMemoryOrderRepository()
    account_id = AccountId.new()
    price = Price(Decimal("101.25"), Currency("USD"))
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.partial_then_fill(
            price=price,
            partial_quantities=(
                Quantity(Decimal("2")),
                Quantity(Decimal("3")),
            ),
        ),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)
    get_order = GetOrder(repository=repository)

    result = submit.execute(
        SubmitOrderCommand(
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("10")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            account_id=account_id,
        )
    )

    print(f"after submit: {result.order.status.value}")

    for report in execution.drain_reports(result.order.order_id):
        snapshot = handle.execute(report)
        print(
            f"report={report.status.value} "
            f"status={snapshot.status.value} "
            f"filled={snapshot.filled_quantity}"
        )

    final = get_order.execute(result.order.order_id)
    if final is None:
        raise RuntimeError("Expected order to remain available in the repository.")

    print(f"final status: {final.status.value}")
    print(f"final filled quantity: {final.filled_quantity}")


if __name__ == "__main__":
    main()
