# Backtesting Guide

## Overview

RunBacktest executes a strategy over an immutable HistoricalDataset while reusing the production-shaped core.

The backtest-specific pieces are:

- BacktestClock
- HistoricalMarketDataAdapter
- SimulatedExecutionAdapter
- execution, cost, slippage, and latency models
- RunManifest
- BacktestReport

Risk, OMS, Fill processing, and Portfolio accounting are reused.

## Build historical bars

Use Bar with UTC timestamps and explicit Price values.

OHLC invariants are enforced at construction.

Wrap each Bar in MarketDataEvent.

Events must already be in strict deterministic order.

## Create a HistoricalDataset

HistoricalDataset identifies one immutable dataset version.

Required metadata includes:

- dataset_id
- version
- checksum
- instruments
- interval
- start_time
- end_time

Use historical_events_checksum on the exact canonical event tuple used by the run.

A checksum mismatch causes the adapter to fail before iteration.

## Configure execution

The P0 release includes:

- SimpleBarExecutionModel
- ZeroCostModel
- FixedFeeModel
- BpsFeeModel
- ZeroSlippage
- FixedBpsSlippage
- ZeroLatency
- FixedEventLatency

All chosen model identities and versions are captured in RunManifest.

## Run a backtest

Construct RunBacktestCommand with:

- Strategy metadata
- StrategyProtocol implementation
- strategy configuration
- HistoricalDataset
- canonical event tuple
- Account
- initial cash
- RiskPolicy
- ContractSpecification by instrument
- execution model
- cost model
- slippage model
- latency model
- deterministic seed

Then execute:

~~~python
report = RunBacktest(authorization_gate=authorization_gate).execute(command)
~~~

## Inspect the report

BacktestReport contains:

- run id
- RunManifest
- start and completion timestamps
- initial NAV
- final PortfolioSnapshot
- BacktestMetrics
- equity curve

BacktestMetrics contains:

- total_return
- absolute_pnl
- max_drawdown
- number_of_orders
- number_of_fills
- risk_rejections

## Deterministic replay

For a deterministic strategy and unchanged inputs:

~~~python
first = RunBacktest(authorization_gate=authorization_gate).execute(command)
second = RunBacktest(authorization_gate=authorization_gate).execute(command)

assert first == second
~~~

This equality includes deterministic run identifiers, manifest, timestamps, final portfolio state, metrics, and equity curve.

## No look-ahead

Do not bypass HistoricalMarketDataAdapter by handing the strategy a full historical table.

The intended access pattern is one validated MarketDataEvent at a time.

An order submitted because of event t is eligible for simulated fill only on a strictly future event.

## Execution assumptions

SimpleBarExecutionModel is intentionally conservative and simple.

It is not an exchange simulator.

It does not model:

- order-book depth
- queue priority
- partial fills
- opening auctions
- corporate actions
- hidden liquidity
- venue-specific microstructure

Those require later explicit models rather than hidden heuristics.
