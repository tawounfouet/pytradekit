"""Deterministic strategy callback runtime."""

from pytradekit.market_data.domain import MarketDataEvent, TimerEvent
from pytradekit.portfolio.domain import PortfolioSnapshot
from pytradekit.runtime.ports import ClockPort
from pytradekit.strategy.domain import (
    StrategyContext,
    StrategyDecision,
    StrategyProtocol,
    StrategyRun,
    StrategyRunStatus,
)
from pytradekit.strategy.ports import StrategyAdmissionPort, StrategyStateStore


class StrategyRuntime:
    """Invoke broker-agnostic strategy code with explicit state and time."""

    def __init__(
        self,
        *,
        implementation: StrategyProtocol,
        run: StrategyRun,
        state_store: StrategyStateStore,
        clock: ClockPort,
        admission: StrategyAdmissionPort | None = None,
    ) -> None:
        self._implementation = implementation
        self._run = run
        self._state_store = state_store
        self._clock = clock
        self._admission = admission

    def process_market_event(
        self,
        event: MarketDataEvent,
        *,
        portfolio: PortfolioSnapshot,
        trading_enabled: bool,
    ) -> StrategyDecision:
        self._require_running()
        effective_trading = self._effective_trading_enabled(
            portfolio=portfolio,
            requested=trading_enabled,
        )
        state = self._state_store.load(self._run.id)
        context = StrategyContext(
            run_id=self._run.id,
            current_time=self._clock.now(),
            portfolio=portfolio,
            state=state,
            trading_enabled=effective_trading,
        )
        decision = self._implementation.on_market_data(event, context)
        self._state_store.save(self._run.id, decision.state)
        self._run.record_state_version(decision.state.version)
        if effective_trading:
            return decision
        return StrategyDecision(
            state=decision.state,
            signals=decision.signals,
            targets=(),
        )

    def process_timer_event(
        self,
        event: TimerEvent,
        *,
        portfolio: PortfolioSnapshot,
        trading_enabled: bool,
    ) -> StrategyDecision:
        self._require_running()
        effective_trading = self._effective_trading_enabled(
            portfolio=portfolio,
            requested=trading_enabled,
        )
        state = self._state_store.load(self._run.id)
        context = StrategyContext(
            run_id=self._run.id,
            current_time=self._clock.now(),
            portfolio=portfolio,
            state=state,
            trading_enabled=effective_trading,
        )
        decision = self._implementation.on_timer(event, context)
        self._state_store.save(self._run.id, decision.state)
        self._run.record_state_version(decision.state.version)
        if effective_trading:
            return decision
        return StrategyDecision(
            state=decision.state,
            signals=decision.signals,
            targets=(),
        )

    def _effective_trading_enabled(
        self,
        *,
        portfolio: PortfolioSnapshot,
        requested: bool,
    ) -> bool:
        if not requested:
            return False
        if self._admission is None:
            return True
        return self._admission.allow_new_targets(portfolio.account_id)

    def _require_running(self) -> None:
        if self._run.status is not StrategyRunStatus.RUNNING:
            raise RuntimeError("StrategyRuntime requires a RUNNING StrategyRun.")
