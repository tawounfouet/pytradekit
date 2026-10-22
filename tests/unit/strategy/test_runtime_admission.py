"""Strategy runtime admission tests for reconciliation safety."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.market_data import TimerEvent
from pytradekit.portfolio.domain import AccountId, PortfolioSnapshot
from pytradekit.shared import Currency, InstrumentId, Money
from pytradekit.strategy import (
    StrategyDecision,
    StrategyId,
    StrategyRun,
    StrategyRunId,
    StrategyState,
    StrategyVersion,
    TargetPosition,
)
from pytradekit.strategy.adapters import InMemoryStrategyStateStore
from pytradekit.strategy.application import StrategyRuntime
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 16, tzinfo=UTC)
USD = Currency("USD")


class RecordingStrategy:
    """Strategy that always requests one target and records admission context."""

    def __init__(self) -> None:
        self.trading_enabled: bool | None = None
        self.instrument_id = InstrumentId.new()

    def on_market_data(self, event: object, context: object) -> StrategyDecision:
        raise AssertionError("market-data path is not used by this test")

    def on_timer(self, event: TimerEvent, context: object) -> StrategyDecision:
        from pytradekit.strategy import StrategyContext

        if not isinstance(context, StrategyContext):
            raise TypeError("context must be StrategyContext")
        self.trading_enabled = context.trading_enabled
        return StrategyDecision(
            state=context.state.evolve({"tick": 1}),
            targets=(
                TargetPosition(
                    instrument_id=self.instrument_id,
                    target_quantity=Decimal("1"),
                ),
            ),
        )


class BlockingAdmission:
    def allow_new_targets(self, account_id: AccountId) -> bool:
        return False


class AllowingAdmission:
    def allow_new_targets(self, account_id: AccountId) -> bool:
        return True


def _portfolio(account_id: AccountId) -> PortfolioSnapshot:
    zero = Money(Decimal("0"), USD)
    return PortfolioSnapshot(
        account_id=account_id,
        as_of=NOW,
        base_currency=USD,
        cash=(),
        positions=(),
        nav=zero,
        gross_exposure=zero,
        net_exposure=zero,
        realized_pnl=zero,
        unrealized_pnl=zero,
        leverage=None,
    )


def _run() -> StrategyRun:
    run = StrategyRun(
        id=StrategyRunId.new(),
        strategy_id=StrategyId.new(),
        strategy_version=StrategyVersion("1.0.0"),
    )
    run.start(at=NOW)
    return run


def test_unsafe_consistency_pauses_strategy_targets_even_when_requested_enabled() -> None:
    strategy = RecordingStrategy()
    account_id = AccountId.new()
    runtime = StrategyRuntime(
        implementation=strategy,
        run=_run(),
        state_store=InMemoryStrategyStateStore(),
        clock=FakeClock(NOW),
        admission=BlockingAdmission(),
    )

    decision = runtime.process_timer_event(
        TimerEvent(name="reconcile-safe", event_time=NOW),
        portfolio=_portfolio(account_id),
        trading_enabled=True,
    )

    assert strategy.trading_enabled is False
    assert decision.targets == ()
    assert decision.state == StrategyState(version=1, values={"tick": 1})


def test_safe_consistency_preserves_strategy_targets() -> None:
    strategy = RecordingStrategy()
    account_id = AccountId.new()
    runtime = StrategyRuntime(
        implementation=strategy,
        run=_run(),
        state_store=InMemoryStrategyStateStore(),
        clock=FakeClock(NOW),
        admission=AllowingAdmission(),
    )

    decision = runtime.process_timer_event(
        TimerEvent(name="reconcile-safe", event_time=NOW),
        portfolio=_portfolio(account_id),
        trading_enabled=True,
    )

    assert strategy.trading_enabled is True
    assert len(decision.targets) == 1
