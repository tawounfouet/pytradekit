# Strategy Guide

## Overview

Strategy code expresses trading intent without talking directly to brokers or ExecutionPort.

The normal semantic path is:

~~~text
market fact
-> Strategy
-> Signal or TargetPosition
-> Portfolio Construction
-> OrderIntent
-> Risk
-> OMS
-> Execution
~~~

## Define strategy metadata

Strategy is immutable metadata:

~~~python
strategy = Strategy(
    id=StrategyId.new(),
    name="Threshold Strategy",
    version=StrategyVersion("1.0.0"),
    requirements=StrategyRequirements(
        instruments=(instrument_id,),
        bar_intervals=("1d",),
        required_order_types=(OrderType.MARKET,),
        warmup_bars=1,
    ),
)
~~~

StrategyRequirements declares what the runtime must provide before execution is considered valid.

## Implement callbacks

A strategy implementation satisfies StrategyProtocol.

It receives one event and one StrategyContext:

~~~python
class ThresholdStrategy:
    def on_market_data(
        self,
        event: MarketDataEvent,
        context: StrategyContext,
    ) -> StrategyDecision:
        ...

    def on_timer(
        self,
        event: TimerEvent,
        context: StrategyContext,
    ) -> StrategyDecision:
        ...
~~~

StrategyContext provides:

- run identity
- current runtime time
- current PortfolioSnapshot
- current explicit StrategyState
- trading_enabled flag

There is no broker handle and no ExecutionPort in StrategyContext.

## Use explicit state

StrategyState is versioned.

A callback returns the next state explicitly:

~~~python
next_state = context.state.evolve({"seen": 4})

return StrategyDecision(
    state=next_state,
)
~~~

The runtime checkpoints that state through StrategyStateStore.

Do not hide mutable trading state in module globals or object side effects.

## Signals

Signal represents an opinion:

~~~text
LONG
SHORT
FLAT
~~~

It can include optional strength and generation time.

A Signal is not a portfolio target and is not an order.

## Target positions

TargetPosition expresses desired portfolio state in exactly one mode:

- target_quantity
- target_notional
- target_weight

Example:

~~~python
TargetPosition(
    instrument_id=instrument_id,
    target_quantity=Decimal("10"),
)
~~~

A strategy can return zero or more targets in StrategyDecision.

## Warmup

StrategyRequirements.warmup_bars delays trading until the runtime has processed enough bars for every required instrument.

Callbacks still run during warmup so state can accumulate.

The runtime suppresses target execution while trading_enabled is false.

## Timers

TimerEvent represents deterministic runtime time, not wall-clock scheduling.

A strategy can use on_timer for runtime-generated events without importing datetime.now() or an operating-system scheduler.

## Design rule

Keep strategy logic focused on:

- market observations
- explicit state
- portfolio observations
- signals
- targets

Do not create Orders directly inside strategy code and do not call a broker.
