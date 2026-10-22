"""Application and fake-broker tests for OMS vertical slices."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.execution import ExecutionReport, ExecutionStatus, Fill, FillId, SubmissionStatus
from pytradekit.orders import ExecutionCertainty, OrderSide, OrderStatus, OrderType, TimeInForce
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
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
USD = Currency("USD")
PRICE = Price(Decimal("100"), USD)
ACCOUNT_ID = AccountId.new()


def _submit_command(*, order_type: OrderType = OrderType.MARKET) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Quantity(Decimal("10")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        account_id=ACCOUNT_ID,
        limit_price=PRICE if order_type is OrderType.LIMIT else None,
    )


def test_market_order_partial_then_full_fill_end_to_end() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    adapter = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.partial_then_fill(
            price=PRICE,
            partial_quantities=(Quantity(Decimal("4")), Quantity(Decimal("3"))),
        ),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)

    submitted = submit.execute(_submit_command())
    assert submitted.order.status is OrderStatus.ACCEPTED

    reports = adapter.drain_reports(submitted.order.order_id)
    assert len(reports) == 4
    for report in reports:
        handle.execute(report)

    final = GetOrder(repository=repository).execute(submitted.order.order_id)
    assert final is not None
    assert final.status is OrderStatus.FILLED
    assert final.filled_quantity == Quantity(Decimal("10"))

    version = final.version
    duplicate_final = reports[-1]
    handle.execute(duplicate_final)
    after_duplicate = GetOrder(repository=repository).execute(submitted.order.order_id)
    assert after_duplicate is not None
    assert after_duplicate.filled_quantity == Quantity(Decimal("10"))
    assert after_duplicate.version == version


def test_limit_order_remains_accepted_until_execution_report() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    adapter = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )

    result = submit.execute(_submit_command(order_type=OrderType.LIMIT))

    assert result.order.status is OrderStatus.ACCEPTED
    assert result.order.limit_price == PRICE


def test_submit_timeout_stays_uncertain_and_converges_by_query() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    adapter = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.submit_timeout(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)

    result = submit.execute(_submit_command())

    assert result.submission_status is SubmissionStatus.UNCERTAIN
    assert result.order.status is OrderStatus.SUBMITTED
    assert result.order.execution_certainty is ExecutionCertainty.UNCERTAIN

    aggregate = repository.get(result.order.order_id)
    assert aggregate is not None
    resolution = adapter.query_order(aggregate)
    assert resolution is not None
    resolved = handle.execute(resolution)
    assert resolved.status is OrderStatus.ACCEPTED
    assert resolved.execution_certainty is ExecutionCertainty.CONFIRMED


def test_cancel_flow_waits_for_execution_report() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    adapter = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)
    cancel = CancelOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )

    result = submit.execute(_submit_command())
    for report in adapter.drain_reports(result.order.order_id):
        handle.execute(report)

    cancellation = cancel.execute(
        CancelOrderCommand(
            order_id=result.order.order_id,
            account_id=ACCOUNT_ID,
        )
    )
    assert cancellation.order.status is OrderStatus.CANCEL_REQUESTED

    for report in adapter.drain_reports(result.order.order_id):
        handle.execute(report)

    final = GetOrder(repository=repository).execute(result.order.order_id)
    assert final is not None
    assert final.status is OrderStatus.CANCELLED


def test_cancel_fill_race_applies_real_fill_before_cancel_confirmation() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    adapter = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)
    cancel = CancelOrder(
        repository=repository,
        execution=adapter,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )

    submitted = submit.execute(_submit_command())
    for report in adapter.drain_reports(submitted.order.order_id):
        handle.execute(report)
    cancel.execute(
        CancelOrderCommand(
            order_id=submitted.order.order_id,
            account_id=ACCOUNT_ID,
        )
    )

    fill = Fill(
        id=FillId.new(),
        order_id=submitted.order.order_id,
        quantity=Quantity(Decimal("4")),
        price=PRICE,
        occurred_at=clock.now(),
        external_fill_id="race-fill-1",
    )
    handle.execute(
        ExecutionReport(
            order_id=submitted.order.order_id,
            status=ExecutionStatus.PARTIALLY_FILLED,
            occurred_at=clock.now(),
            correlation_id=CorrelationId.new(),
        account_id=ACCOUNT_ID,
            external_order_id=submitted.order.external_order_id,
            fill=fill,
        )
    )

    mid = GetOrder(repository=repository).execute(submitted.order.order_id)
    assert mid is not None
    assert mid.status is OrderStatus.PARTIALLY_FILLED
    assert mid.filled_quantity == Quantity(Decimal("4"))

    for report in adapter.drain_reports(submitted.order.order_id):
        handle.execute(report)

    final = GetOrder(repository=repository).execute(submitted.order.order_id)
    assert final is not None
    assert final.status is OrderStatus.CANCELLED
    assert final.filled_quantity == Quantity(Decimal("4"))
