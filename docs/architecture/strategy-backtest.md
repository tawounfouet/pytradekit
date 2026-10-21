# Strategy & Backtest Architecture

## Purpose

PyTradeKit 0.4 adds strategy execution and historical backtesting without creating a second trading system.

The central design constraint is:

~~~text
Backtest orchestrates existing core semantics.
Backtest does not replace them.
~~~

Risk, OMS, Order, ExecutionReport, Fill, and Portfolio remain canonical across simulation and later broker modes.

## Semantic boundaries

Four concepts are intentionally distinct:

~~~text
Signal
!= TargetPosition
!= OrderIntent
!= Order
~~~

Signal is a strategy opinion.

TargetPosition is desired portfolio state.

OrderIntent is portfolio-construction output describing a required trade.

Order is the canonical OMS aggregate and is created only when the normal submission path is entered.

This separation prevents strategy code from bypassing Risk or OMS.

## Strategy domain

The strategy bounded surface contains:

- StrategyId
- StrategyVersion
- Strategy
- StrategyRequirements
- StrategyRunId
- StrategyRunStatus
- StrategyRun
- StrategyState
- StrategyContext
- StrategyDecision
- Signal
- TargetPosition
- OrderIntent
- StrategyProtocol

StrategyRun owns lifecycle state for one concrete execution.

StrategyState is explicit, versioned, and stored through StrategyStateStore.

StrategyRuntime loads state before a callback and checkpoints the returned state after the callback.

## Market-data domain

Historical data is represented by canonical immutable domain values:

- Bar
- MarketDataEvent
- TimerEvent
- HistoricalDataset
- DataQuality

Bar enforces OHLC and UTC time invariants.

HistoricalDataset carries identity, version, checksum, instrument set, interval, time range, schema version, adjustment mode, and source.

The dataset checksum covers canonical event semantics in deterministic order.

## Deterministic time

BacktestClock is controlled by the runtime.

It:

- starts from an explicit UTC timestamp
- advances only to an explicit future timestamp
- never moves backwards
- does not read wall-clock time

HistoricalMarketDataAdapter advances BacktestClock immediately before yielding each validated event.

Therefore strategy callbacks observe the runtime time corresponding to the event currently being processed.

## No-look-ahead boundary

The strategy is given one MarketDataEvent and current StrategyContext.

It is not handed an entire historical DataFrame.

The runtime guarantee is:

~~~text
at event time t
Strategy sees current event data
and portfolio/state facts available at t
but not future events
~~~

HistoricalMarketDataAdapter validates:

- non-empty event set
- dataset checksum
- allowed instruments
- matching interval
- dataset time range
- duplicate bars
- strict deterministic ordering

## Portfolio construction

Strategy produces TargetPosition, not Order.

RebalanceService receives:

~~~text
TargetPosition
+ current PortfolioSnapshot
+ reference Price
+ ContractSpecification
~~~

and computes:

~~~text
target quantity - current quantity = delta
~~~

A zero delta produces no OrderIntent.

A positive delta produces BUY.

A negative delta produces SELL.

Quantity is quantized to ContractSpecification.quantity_step before intent creation.

## Simulated execution

SimulatedExecutionAdapter implements the canonical Orders ExecutionPort.

It does not define BacktestOrder or a second OMS.

The adapter stores acknowledged pending Orders and evaluates them only against future eligible MarketDataEvent values.

P0 execution semantics are:

~~~text
MARKET
-> next eligible bar open

BUY LIMIT
-> fill when next eligible future bar low <= limit

SELL LIMIT
-> fill when next eligible future bar high >= limit
~~~

Slippage is applied after the execution model determines a base price.

Cost is calculated from side, quantity, and slipped fill price.

Latency is expressed as the number of future eligible events that must pass before fill evaluation.

## Runtime orchestration

RunBacktest assembles the milestone pipeline:

~~~text
historical event
-> advance BacktestClock
-> process eligible simulated fills
-> update canonical OMS state
-> apply canonical Fill to Portfolio
-> build PortfolioSnapshot
-> expose snapshot to Risk
-> load StrategyState
-> invoke Strategy
-> TargetPosition
-> RebalanceService
-> OrderIntent
-> SubmitOrder
-> projected Risk
-> canonical OMS
-> SimulatedExecutionAdapter
-> checkpoint StrategyState
-> record equity point
~~~

The important property is ownership:

~~~text
Backtest owns orchestration and adapters.
Backtest does not own Risk.
Backtest does not own OMS.
Backtest does not own Portfolio.
~~~

## Reproducibility

RunManifest records the semantic environment of one run:

- PyTradeKit version
- StrategyId
- StrategyVersion
- strategy configuration hash
- dataset id
- dataset version
- dataset checksum
- RiskPolicy id
- RiskPolicy version
- execution model identity/version
- cost model identity/version
- slippage model identity/version
- latency model identity/version
- random seed
- runtime profile
- deterministic start timestamp

RunManifest.fingerprint is stable for the same manifest values.

The runtime derives deterministic identifiers from this fingerprint for:

- StrategyRunId
- BacktestRunId
- OrderId
- CorrelationId

Simulated fill identity is derived from order identity, event timestamp, and quantity.

## Golden Backtest

The Golden Backtest qualifies a fixed threshold strategy on a fixed immutable dataset.

Expected economics:

~~~text
initial NAV: 10000 USD
final NAV:   10020 USD
orders:      2
fills:       2
risk rejects: 0
return:      0.002
max drawdown: 0
~~~

Running the same command twice produces equal BacktestReport values.

## Architecture guarantees

CI enforces:

- Strategy domain cannot import brokers
- Strategy domain cannot import backtesting adapters
- Market-data domain cannot import Strategy
- Market-data domain cannot import brokers
- runtime ports do not depend on adapters
- prior Portfolio, Risk, Orders, and shared-kernel boundaries remain intact

## Explicit non-goals

Milestone 0.4 does not add:

- real broker connectivity
- durable persistence
- process restart recovery
- broker reconciliation
- corporate actions
- advanced exchange microstructure
- distributed backtest workers
- production operations
