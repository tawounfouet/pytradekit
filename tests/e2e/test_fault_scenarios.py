"""Fault and race qualification for milestone 0.2."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.execution import (
    ExecutionReport,
    ExecutionStatus,
    Fill,
    FillId,
    SubmissionStatus,
)
from pytradekit.orders import (
    ExecutionCertainty,
    Order,
    OrderId,
    OrderNotCancellableError,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
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
PRICE = Price(Decimal("99.50"), USD)
ACCOUNT_ID = AccountId.new()


def _command() -> SubmitOrderCommand:
    return SubmitOrderCommand(
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("10")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        account_id=ACCOUNT_ID,
    )


def test_submit_timeout_converges_to_acceptance_by_query() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.submit_timeout(resolve_as=ExecutionStatus.ACCEPTED),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)

    submitted = submit.execute(_command())
    assert submitted.submission_status is SubmissionStatus.UNCERTAIN
    assert submitted.order.status is OrderStatus.SUBMITTED
    assert submitted.order.execution_certainty is ExecutionCertainty.UNCERTAIN

    aggregate = repository.get(submitted.order.order_id)
    assert aggregate is not None
    resolution = execution.query_order(aggregate)
    assert resolution is not None

    resolved = handle.execute(resolution)
    assert resolved.status is OrderStatus.ACCEPTED
    assert resolved.execution_certainty is ExecutionCertainty.CONFIRMED


def test_submit_timeout_can_converge_to_rejection_by_query() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.submit_timeout(resolve_as=ExecutionStatus.REJECTED),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)

    submitted = submit.execute(_command())
    aggregate = repository.get(submitted.order.order_id)
    assert aggregate is not None
    resolution = execution.query_order(aggregate)
    assert resolution is not None

    resolved = handle.execute(resolution)
    assert resolved.status is OrderStatus.REJECTED
    assert resolved.execution_certainty is ExecutionCertainty.CONFIRMED


def test_duplicate_fill_has_exactly_one_economic_effect() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.fill_immediately(price=PRICE),
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

    submitted = submit.execute(_command())
    reports = execution.drain_reports(submitted.order.order_id)
    fill_report = reports[-1]

    handle.execute(fill_report)
    after_first = get_order.execute(submitted.order.order_id)
    assert after_first is not None
    version_after_first = after_first.version

    handle.execute(fill_report)
    after_duplicate = get_order.execute(submitted.order.order_id)
    assert after_duplicate is not None
    assert after_duplicate.status is OrderStatus.FILLED
    assert after_duplicate.filled_quantity == Quantity(Decimal("10"))
    assert after_duplicate.version == version_after_first


def test_fill_before_acceptance_does_not_regress_when_acceptance_arrives_late() -> None:
    repository = InMemoryOrderRepository()
    correlation_id = CorrelationId.new()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("10")),
        time_in_force=TimeInForce.DAY,
        correlation_id=correlation_id,
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    repository.add(order)
    handle = HandleExecutionReport(repository=repository)

    fill = Fill(
        id=FillId.new(),
        order_id=order.id,
        quantity=Quantity(Decimal("4")),
        price=PRICE,
        occurred_at=NOW,
        external_fill_id="out-of-order-fill-1",
    )
    partial = handle.execute(
        ExecutionReport(
            order_id=order.id,
            status=ExecutionStatus.PARTIALLY_FILLED,
            occurred_at=NOW,
            correlation_id=correlation_id,
            external_order_id="broker-order-1",
            fill=fill,
        )
    )
    assert partial.status is OrderStatus.PARTIALLY_FILLED
    version_after_fill = partial.version

    late_acceptance = handle.execute(
        ExecutionReport(
            order_id=order.id,
            status=ExecutionStatus.ACCEPTED,
            occurred_at=NOW,
            correlation_id=correlation_id,
            external_order_id="broker-order-1",
        )
    )
    assert late_acceptance.status is OrderStatus.PARTIALLY_FILLED
    assert late_acceptance.version == version_after_fill


def test_cancel_timeout_stays_uncertain_and_blocks_blind_resubmission() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.cancel_timeout(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    cancel = CancelOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )

    submitted = submit.execute(_command())
    cancellation = cancel.execute(
        CancelOrderCommand(
            order_id=submitted.order.order_id,
            account_id=ACCOUNT_ID,
        )
    )

    assert cancellation.order.status is OrderStatus.CANCEL_REQUESTED
    assert cancellation.order.execution_certainty is ExecutionCertainty.UNCERTAIN

    with pytest.raises(OrderNotCancellableError):
        cancel.execute(
        CancelOrderCommand(
            order_id=submitted.order.order_id,
            account_id=ACCOUNT_ID,
        )
    )


def test_full_fill_wins_over_late_cancel_confirmation() -> None:
    clock = FakeClock.at(NOW)
    repository = InMemoryOrderRepository()
    execution = FakeExecutionAdapter(
        scenario=FakeExecutionScenario.accept_immediately(),
        clock=clock,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    cancel = CancelOrder(
        repository=repository,
        execution=execution,
        clock=clock,
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    handle = HandleExecutionReport(repository=repository)
    get_order = GetOrder(repository=repository)

    submitted = submit.execute(_command())
    execution.drain_reports(submitted.order.order_id)
    cancel.execute(
        CancelOrderCommand(
            order_id=submitted.order.order_id,
            account_id=ACCOUNT_ID,
        )
    )
    cancel_reports = execution.drain_reports(submitted.order.order_id)

    fill = Fill(
        id=FillId.new(),
        order_id=submitted.order.order_id,
        quantity=Quantity(Decimal("10")),
        price=PRICE,
        occurred_at=NOW,
        external_fill_id="cancel-race-fill-1",
    )
    handle.execute(
        ExecutionReport(
            order_id=submitted.order.order_id,
            status=ExecutionStatus.FILLED,
            occurred_at=NOW,
            correlation_id=CorrelationId.new(),
        account_id=ACCOUNT_ID,
            external_order_id=submitted.order.external_order_id,
            fill=fill,
        )
    )

    for report in cancel_reports:
        handle.execute(report)

    final = get_order.execute(submitted.order.order_id)
    assert final is not None
    assert final.status is OrderStatus.FILLED
    assert final.filled_quantity == Quantity(Decimal("10"))
