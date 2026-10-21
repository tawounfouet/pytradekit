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
from pytradekit.strategy.ports import StrategyStateStore


class StrategyRuntime:
    """Invoke broker-agnostic strategy code with explicit state and time."""

    def __init__(
        self,
        *,
        implementation: StrategyProtocol,
        run: StrategyRun,
        state_store: StrategyStateStore,
        clock: ClockPort,
    ) -> None:
        self._implementation = implementation
        self._run = run
        self._state_store = state_store
        self._clock = clock

    def process_market_event(
        self,
        event: MarketDataEvent,
        *,
        portfolio: PortfolioSnapshot,
        trading_enabled: bool,
    ) -> StrategyDecision:
        self._require_running()
        state = self._state_store.load(self._run.id)
        context = StrategyContext(
            run_id=self._run.id,
            current_time=self._clock.now(),
            portfolio=portfolio,
            state=state,
            trading_enabled=trading_enabled,
        )
        decision = self._implementation.on_market_data(event, context)
        self._state_store.save(self._run.id, decision.state)
        self._run.record_state_version(decision.state.version)
        if trading_enabled:
            return decision
        return StrategyDecision(state=decision.state, signals=decision.signals, targets=())

    def process_timer_event(
        self,
        event: TimerEvent,
        *,
        portfolio: PortfolioSnapshot,
        trading_enabled: bool,
    ) -> StrategyDecision:
        self._require_running()
        state = self._state_store.load(self._run.id)
        context = StrategyContext(
            run_id=self._run.id,
            current_time=self._clock.now(),
            portfolio=portfolio,
            state=state,
            trading_enabled=trading_enabled,
        )
        decision = self._implementation.on_timer(event, context)
        self._state_store.save(self._run.id, decision.state)
        self._run.record_state_version(decision.state.version)
        if trading_enabled:
            return decision
        return StrategyDecision(state=decision.state, signals=decision.signals, targets=())

    def _require_running(self) -> None:
        if self._run.status is not StrategyRunStatus.RUNNING:
            raise RuntimeError("StrategyRuntime requires a RUNNING StrategyRun.")
