"""Operational admission control and graceful shutdown for qualified runtimes."""

from __future__ import annotations

import signal
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from threading import Condition
from time import monotonic
from types import FrameType
from typing import Iterator, Protocol

from pytradekit.execution import CancelResult, ExecutionReport, SubmissionResult
from pytradekit.orders.domain import Order
from pytradekit.orders.ports import ExecutionPort
from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.runtime.trading_readiness import TradingReadinessReport


class RuntimeLifecycleState(StrEnum):
    """Operational lifecycle of one trading runtime process."""

    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class RuntimeAdmissionClosedError(RuntimeError):
    """Raised when new economic admission is closed."""


class RuntimeAdmissionGate:
    """Thread-safe admission gate for new economic submissions."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._state = RuntimeLifecycleState.STARTING
        self._active_submissions = 0

    @property
    def state(self) -> RuntimeLifecycleState:
        """Return current lifecycle state."""

        with self._condition:
            return self._state

    @property
    def active_submissions(self) -> int:
        """Return number of submissions currently inside the execution boundary."""

        with self._condition:
            return self._active_submissions

    def mark_ready(self) -> None:
        """Open new submission admission."""

        with self._condition:
            self._state = RuntimeLifecycleState.READY
            self._condition.notify_all()

    def mark_degraded(self) -> None:
        """Close submission admission while keeping the process observable."""

        with self._condition:
            self._state = RuntimeLifecycleState.DEGRADED
            self._condition.notify_all()

    def begin_draining(self) -> None:
        """Close new submissions while allowing cancellations and reads."""

        with self._condition:
            if self._state is RuntimeLifecycleState.STOPPED:
                return
            self._state = RuntimeLifecycleState.DRAINING
            self._condition.notify_all()

    def mark_stopped(self) -> None:
        """Close every execution operation."""

        with self._condition:
            self._state = RuntimeLifecycleState.STOPPED
            self._condition.notify_all()

    @contextmanager
    def submission_slot(self) -> Iterator[None]:
        """Admit one submission only while the runtime is READY."""

        with self._condition:
            if self._state is not RuntimeLifecycleState.READY:
                raise RuntimeAdmissionClosedError(
                    f"New submissions are closed while runtime is {self._state.value}."
                )
            self._active_submissions += 1

        try:
            yield
        finally:
            with self._condition:
                self._active_submissions -= 1
                self._condition.notify_all()

    def ensure_cancel_allowed(self) -> None:
        """Permit risk-reducing cancellation during READY or DRAINING."""

        with self._condition:
            if self._state not in {
                RuntimeLifecycleState.READY,
                RuntimeLifecycleState.DRAINING,
            }:
                raise RuntimeAdmissionClosedError(
                    f"Cancellation is unavailable while runtime is {self._state.value}."
                )

    def ensure_query_allowed(self) -> None:
        """Permit read-side reconciliation until the process is fully stopped."""

        with self._condition:
            if self._state is RuntimeLifecycleState.STOPPED:
                raise RuntimeAdmissionClosedError("Runtime is stopped.")

    def wait_for_submissions(self, timeout: float) -> bool:
        """Wait bounded time for already-admitted submissions to return."""

        if timeout < 0:
            raise ValueError("Drain timeout must be non-negative.")
        deadline = monotonic() + timeout
        with self._condition:
            while self._active_submissions:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True


class AdmissionControlledExecutionPort:
    """ExecutionPort wrapper enforcing runtime admission state."""

    def __init__(
        self,
        *,
        delegate: ExecutionPort,
        gate: RuntimeAdmissionGate,
    ) -> None:
        self._delegate = delegate
        self._gate = gate

    def submit(self, order: Order) -> SubmissionResult:
        """Submit only when the runtime is TRADING_READY."""

        with self._gate.submission_slot():
            return self._delegate.submit(order)

    def cancel(self, order: Order) -> CancelResult:
        """Allow cancellation while ready or draining."""

        self._gate.ensure_cancel_allowed()
        return self._delegate.cancel(order)

    def query_order(self, order: Order) -> ExecutionReport | None:
        """Allow reconciliation reads until the runtime has fully stopped."""

        self._gate.ensure_query_allowed()
        return self._delegate.query_order(order)


class StartStopRuntime(Protocol):
    """Runtime surface supervised by the production lifecycle controller."""

    def start(self) -> TradingReadinessReport:
        """Start and reconcile the runtime."""

        ...

    def stop(self) -> None:
        """Stop provider streaming and runtime services."""

        ...


@dataclass(frozen=True, slots=True)
class ShutdownReport:
    """Result of one graceful shutdown attempt."""

    drained: bool
    forced: bool
    final_state: RuntimeLifecycleState
    active_submissions_at_timeout: int


class ProductionRuntimeSupervisor:
    """Connect trading readiness to admission, signals, shutdown, and metrics."""

    def __init__(
        self,
        *,
        runtime: StartStopRuntime,
        gate: RuntimeAdmissionGate | None = None,
        observer: RuntimeObserver | None = None,
    ) -> None:
        self._runtime = runtime
        self.gate = gate or RuntimeAdmissionGate()
        self.observer = observer or RuntimeObserver()
        self._last_readiness: TradingReadinessReport | None = None

    @property
    def last_readiness(self) -> TradingReadinessReport | None:
        """Return the latest full trading readiness report."""

        return self._last_readiness

    def start(self) -> TradingReadinessReport:
        """Start the runtime and open admission only on TRADING_READY."""

        self.observer.increment("runtime_start_attempts")
        self.observer.event("runtime_starting")
        try:
            report = self._runtime.start()
        except Exception as exc:
            self.gate.mark_degraded()
            self.observer.increment("runtime_start_failures")
            self.observer.set_gauge("trading_ready", 0)
            self.observer.event(
                "runtime_start_failed",
                error_type=type(exc).__name__,
            )
            raise

        self._last_readiness = report
        if report.trading_ready:
            self.gate.mark_ready()
            self.observer.increment("runtime_ready_transitions")
            self.observer.set_gauge("trading_ready", 1)
            self.observer.event("runtime_trading_ready")
        else:
            self.gate.mark_degraded()
            self.observer.increment("runtime_not_ready")
            self.observer.set_gauge("trading_ready", 0)
            self.observer.event(
                "runtime_not_ready",
                gap_count=len(report.gaps),
            )
        return report

    def shutdown(self, *, timeout: float = 10.0) -> ShutdownReport:
        """Stop new submissions, drain bounded in-flight work, then stop the runtime."""

        self.observer.increment("runtime_shutdown_attempts")
        self.gate.begin_draining()
        self.observer.set_gauge("trading_ready", 0)
        self.observer.event("runtime_draining")

        drained = self.gate.wait_for_submissions(timeout)
        active_at_timeout = self.gate.active_submissions
        if drained:
            self.observer.increment("runtime_graceful_shutdowns")
        else:
            self.observer.increment("runtime_forced_shutdowns")

        self._runtime.stop()
        self.gate.mark_stopped()
        self.observer.event(
            "runtime_stopped",
            drained=drained,
            active_submissions=active_at_timeout,
        )
        return ShutdownReport(
            drained=drained,
            forced=not drained,
            final_state=RuntimeLifecycleState.STOPPED,
            active_submissions_at_timeout=active_at_timeout,
        )

    def handle_signal(
        self,
        signum: int,
        frame: FrameType | None,
    ) -> None:
        """Handle SIGTERM or SIGINT with the normal bounded shutdown path."""

        _ = frame
        self.observer.event(
            "runtime_signal_received",
            signal_number=signum,
        )
        self.shutdown()

    def install_signal_handlers(self) -> None:
        """Install SIGTERM and SIGINT handlers in the current main thread."""

        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)


def build_admission_controlled_execution(
    *,
    execution: ExecutionPort,
    supervisor: ProductionRuntimeSupervisor,
) -> AdmissionControlledExecutionPort:
    """Wrap one broker execution adapter with the supervisor admission gate."""

    return AdmissionControlledExecutionPort(
        delegate=execution,
        gate=supervisor.gate,
    )
