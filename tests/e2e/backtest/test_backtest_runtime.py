from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pytradekit.backtesting import (
    RunBacktest,
    RunBacktestCommand,
    SimpleBarExecutionModel,
    ZeroCostModel,
    ZeroLatency,
    ZeroSlippage,
)
from pytradekit.backtesting.adapters import historical_events_checksum
from pytradekit.market_data import Bar, HistoricalDataset, MarketDataEvent, TimerEvent
from pytradekit.orders.domain import OrderType
from pytradekit.portfolio.domain import Account, AccountId
from pytradekit.reference import ContractSpecification
from pytradekit.risk.domain import RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.risk.domain.rules import MaxPositionSize
from pytradekit.shared import Currency, InstrumentId, Money, Price
from pytradekit.strategy import (
    Strategy,
    StrategyContext,
    StrategyDecision,
    StrategyId,
    StrategyRequirements,
    StrategyVersion,
    TargetPosition,
)
from pytradekit.testing import (
    ExplicitTestOrderAuthorizationGate,
    ExplicitTestOrderSafetyGate,
)


class GoldenStrategy:
    """Deterministic threshold strategy used to qualify the runtime, not alpha."""

    def on_market_data(
        self,
        event: MarketDataEvent,
        context: StrategyContext,
    ) -> StrategyDecision:
        raw_seen = context.state.values.get("seen", 0)
        seen = raw_seen if isinstance(raw_seen, int) else 0
        state = context.state.evolve({"seen": seen + 1})
        close = event.bar.close.value
        if close >= Decimal("103"):
            target = Decimal("0")
        elif close >= Decimal("101"):
            target = Decimal("10")
        else:
            return StrategyDecision(state=state)
        return StrategyDecision(
            state=state,
            targets=(
                TargetPosition(
                    instrument_id=event.instrument_id,
                    target_quantity=target,
                ),
            ),
        )

    def on_timer(self, event: TimerEvent, context: StrategyContext) -> StrategyDecision:
        return StrategyDecision(state=context.state)


def _golden_inputs() -> RunBacktestCommand:
    usd = Currency("USD")
    instrument_id = InstrumentId(UUID("00000000-0000-0000-0000-000000000101"))
    account_id = AccountId(UUID("00000000-0000-0000-0000-000000000201"))
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = (
        ("100", "101", "99", "100"),
        ("101", "102", "100", "101"),
        ("102", "104", "101", "103"),
        ("104", "105", "103", "104"),
    )
    events: list[MarketDataEvent] = []
    for index, (open_value, high, low, close) in enumerate(values):
        day = start + timedelta(days=index)
        events.append(
            MarketDataEvent(
                bar=Bar(
                    instrument_id=instrument_id,
                    interval="1d",
                    open=Price(Decimal(open_value), usd),
                    high=Price(Decimal(high), usd),
                    low=Price(Decimal(low), usd),
                    close=Price(Decimal(close), usd),
                    start_time=day,
                    end_time=day + timedelta(hours=16),
                ),
                source_sequence=index,
            )
        )
    frozen_events = tuple(events)
    dataset = HistoricalDataset(
        dataset_id="golden-equity-1d",
        version="1",
        checksum=historical_events_checksum(frozen_events),
        instruments=(instrument_id,),
        interval="1d",
        start_time=start,
        end_time=start + timedelta(days=3, hours=16),
    )
    strategy = Strategy(
        id=StrategyId(UUID("00000000-0000-0000-0000-000000000301")),
        name="Golden Threshold Strategy",
        version=StrategyVersion("1.0.0"),
        requirements=StrategyRequirements(
            instruments=(instrument_id,),
            bar_intervals=("1d",),
            required_order_types=(OrderType.MARKET,),
            warmup_bars=1,
        ),
    )
    policy = RiskPolicy(
        id=RiskPolicyId(UUID("00000000-0000-0000-0000-000000000401")),
        name="golden-max-position",
        scope=RiskScope.GLOBAL,
        limits=(MaxPositionSize(max_quantity=Decimal("20")),),
        enabled=True,
        version=1,
    )
    return RunBacktestCommand(
        strategy=strategy,
        implementation=GoldenStrategy(),
        strategy_config={"entry_close": "101", "exit_close": "103"},
        dataset=dataset,
        events=frozen_events,
        account=Account(id=account_id, base_currency=usd, name="golden"),
        initial_cash=Money(Decimal("10000"), usd),
        risk_policy=policy,
        contract_specs={instrument_id: ContractSpecification(quantity_step=Decimal("1"))},
        execution_model=SimpleBarExecutionModel(),
        cost_model=ZeroCostModel(),
        slippage_model=ZeroSlippage(),
        latency_model=ZeroLatency(),
        seed=42,
    )


def test_golden_backtest_reuses_core_and_has_expected_economics() -> None:
    report = RunBacktest(
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=ExplicitTestOrderSafetyGate(),
    ).execute(_golden_inputs())
    assert report.final_nav.amount == Decimal("10020")
    assert report.metrics.number_of_orders == 2
    assert report.metrics.number_of_fills == 2
    assert report.metrics.risk_rejections == 0
    assert report.metrics.total_return == Decimal("0.002")
    assert report.metrics.max_drawdown == Decimal("0")


def test_same_manifest_replays_to_same_semantic_report() -> None:
    first = RunBacktest(
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=ExplicitTestOrderSafetyGate(),
    ).execute(_golden_inputs())
    second = RunBacktest(
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=ExplicitTestOrderSafetyGate(),
    ).execute(_golden_inputs())
    assert first == second
