"""Unit tests for admission control and graceful production shutdown."""

from __future__ import annotations

import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, Thread

import pytest

from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders.domain import (
    Order,
    OrderId,
    OrderSide,
    TimeInForce,
)
from pytradekit.runtime import ReadinessCheck, ReadinessCheckStatus
from pytradekit.runtime.observability import (
    InMemoryOperationalEventSink,
    RuntimeObserver,
)
from pytradekit.runtime.operations import (
    AdmissionControlledExecutionPort,
    ProductionRuntimeSupervisor,
    RuntimeAdmissionClosedError,
    RuntimeAdmissionGate,
    RuntimeLifecycleState,
)
from pytradekit.runtime.trading_readiness import TradingReadinessReport
from pytradekit.shared import CorrelationId, InstrumentId, Quantity

NOW = datetime(2026, 10, 22, 14, 0, tzinfo=UTC)


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


class _Execution:
    def __init__(self) -> None:
        self.submit_entered = Event()
        self.submit_release = Event()
        self.cancel_calls = 0
        self.query_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        _ = order
        self.submit_entered.set()
        self.submit_release.wait(timeout=2)
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id="provider-order",
        )

    def cancel(self, order: Order) -> CancelResult:
        _ = order
        self.cancel_calls += 1
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> None:
        _ = order
        self.query_calls += 1
        return None


@dataclass
class _Runtime:
    ready: bool = True
    starts: int = 0
    stops: int = 0

    def start(self) -> TradingReadinessReport:
        self.starts += 1
        return TradingReadinessReport(
            provider="alpaca",
            environment="PAPER",
            account="********1234",
            checks=(
                ReadinessCheck(
                    name="qualified",
                    status=(
                        ReadinessCheckStatus.PASS
                        if self.ready
                        else ReadinessCheckStatus.FAIL
                    ),
                    detail="qualification",
                ),
            ),
            gaps=() if self.ready else ("synthetic gap",),
        )

    def stop(self) -> None:
        self.stops += 1


def test_submit_is_blocked_until_trading_ready() -> None:
    gate = RuntimeAdmissionGate()
    execution = _Execution()
    adapter = AdmissionControlledExecutionPort(
        delegate=execution,
        gate=gate,
    )

    with pytest.raises(RuntimeAdmissionClosedError):
        adapter.submit(_order())

    gate.mark_ready()
    execution.submit_release.set()
    result = adapter.submit(_order())

    assert result.status is SubmissionStatus.ACKNOWLEDGED


def test_draining_blocks_new_submit_but_keeps_cancel_available() -> None:
    gate = RuntimeAdmissionGate()
    gate.mark_ready()
    gate.begin_draining()
    execution = _Execution()
    adapter = AdmissionControlledExecutionPort(
        delegate=execution,
        gate=gate,
    )

    with pytest.raises(RuntimeAdmissionClosedError):
        adapter.submit(_order())

    result = adapter.cancel(_order())
    assert result.status is CancelStatus.ACKNOWLEDGED
    assert execution.cancel_calls == 1


def test_shutdown_waits_for_admitted_submission_then_stops() -> None:
    runtime = _Runtime()
    gate = RuntimeAdmissionGate()
    sink = InMemoryOperationalEventSink()
    observer = RuntimeObserver(sink=sink)
    supervisor = ProductionRuntimeSupervisor(
        runtime=runtime,
        gate=gate,
        observer=observer,
    )
    assert supervisor.start().trading_ready is True

    execution = _Execution()
    adapter = AdmissionControlledExecutionPort(
        delegate=execution,
        gate=gate,
    )

    worker = Thread(target=lambda: adapter.submit(_order()))
    worker.start()
    assert execution.submit_entered.wait(timeout=1)

    result_box = []

    def shutdown() -> None:
        result_box.append(supervisor.shutdown(timeout=1))

    shutdown_worker = Thread(target=shutdown)
    shutdown_worker.start()
    execution.submit_release.set()
    worker.join(timeout=1)
    shutdown_worker.join(timeout=1)

    report = result_box[0]
    assert report.drained is True
    assert report.forced is False
    assert report.final_state is RuntimeLifecycleState.STOPPED
    assert runtime.stops == 1
    assert observer.metrics.snapshot().gauges["trading_ready"] == 0


def test_shutdown_timeout_is_observable_as_forced() -> None:
    runtime = _Runtime()
    gate = RuntimeAdmissionGate()
    supervisor = ProductionRuntimeSupervisor(
        runtime=runtime,
        gate=gate,
    )
    supervisor.start()

    execution = _Execution()
    adapter = AdmissionControlledExecutionPort(
        delegate=execution,
        gate=gate,
    )
    worker = Thread(target=lambda: adapter.submit(_order()))
    worker.start()
    assert execution.submit_entered.wait(timeout=1)

    report = supervisor.shutdown(timeout=0)

    assert report.forced is True
    assert report.active_submissions_at_timeout == 1
    assert runtime.stops == 1

    execution.submit_release.set()
    worker.join(timeout=1)


def test_not_ready_start_keeps_admission_closed() -> None:
    runtime = _Runtime(ready=False)
    supervisor = ProductionRuntimeSupervisor(runtime=runtime)

    report = supervisor.start()

    assert report.trading_ready is False
    assert supervisor.gate.state is RuntimeLifecycleState.DEGRADED


def test_sigterm_handler_uses_same_shutdown_path() -> None:
    runtime = _Runtime()
    supervisor = ProductionRuntimeSupervisor(runtime=runtime)
    supervisor.start()

    supervisor.handle_signal(signal.SIGTERM, None)

    assert supervisor.gate.state is RuntimeLifecycleState.STOPPED
    assert runtime.stops == 1
