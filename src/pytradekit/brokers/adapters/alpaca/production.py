"""Production operational shell for the fully assembled Alpaca PAPER runtime."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.runtime.operations import (
    AdmissionControlledExecutionPort,
    ProductionRuntimeSupervisor,
    RuntimeAdmissionGate,
    ShutdownReport,
)
from pytradekit.runtime.trading_readiness import TradingReadinessReport

from .startup import AlpacaPaperRuntimeSystem


@dataclass(slots=True)
class QualifiedAlpacaPaperRuntime:
    """Runtime system with admission control, lifecycle supervision, and metrics."""

    system: AlpacaPaperRuntimeSystem
    supervisor: ProductionRuntimeSupervisor
    execution: AdmissionControlledExecutionPort
    observer: RuntimeObserver

    def start(self) -> TradingReadinessReport:
        """Start reconciliation and open admission only after TRADING_READY."""

        return self.supervisor.start()

    def stop(self, *, timeout: float = 10.0) -> ShutdownReport:
        """Drain admitted submissions and stop provider streaming."""

        return self.supervisor.shutdown(timeout=timeout)

    def install_signal_handlers(self) -> None:
        """Install SIGTERM and SIGINT graceful shutdown handlers."""

        self.supervisor.install_signal_handlers()


def build_qualified_alpaca_paper_runtime(
    system: AlpacaPaperRuntimeSystem,
    *,
    observer: RuntimeObserver | None = None,
    gate: RuntimeAdmissionGate | None = None,
) -> QualifiedAlpacaPaperRuntime:
    """Wrap a LOT-09 system with LOT-10 production operational controls."""

    effective_observer = observer or RuntimeObserver()
    supervisor = ProductionRuntimeSupervisor(
        runtime=system,
        gate=gate,
        observer=effective_observer,
    )
    execution = AdmissionControlledExecutionPort(
        delegate=system.execution,
        gate=supervisor.gate,
    )
    return QualifiedAlpacaPaperRuntime(
        system=system,
        supervisor=supervisor,
        execution=execution,
        observer=effective_observer,
    )