# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit financial semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

PyTradeKit 0.4.0 - Strategy & Backtest Runtime

PyTradeKit 0.4 adds a broker-agnostic strategy runtime and deterministic historical backtesting while reusing the same Risk, OMS, Fill, and Portfolio core introduced by earlier milestones.

The milestone remains fully local and simulated. It does not connect to a real broker or submit live trades.

## Requirements

- Python 3.12+
- no runtime dependencies for milestone 0.4

## Development setup

~~~bash
git clone https://github.com/tawounfouet/pytradekit.git
cd pytradekit

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

make check
~~~

On Windows PowerShell:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

## Version

~~~bash
pytradekit --version
~~~

Current release version:

~~~text
0.4.0
~~~

## Milestone flow

~~~text
HistoricalDataset
-> validated MarketDataEvent timeline
-> BacktestClock
-> StrategyRuntime
-> Signal / TargetPosition
-> Portfolio Construction
-> OrderIntent
-> Risk
-> OMS
-> SimulatedExecutionAdapter
-> ExecutionReport / Fill
-> Portfolio
-> BacktestReport
~~~

Backtest does not own a parallel Risk engine, OMS, Order model, Fill model, or Portfolio model.

## Strategy semantics

PyTradeKit keeps four concepts separate:

~~~text
Signal
!= TargetPosition
!= OrderIntent
!= Order
~~~

- Signal expresses a market view.
- TargetPosition expresses desired portfolio state.
- OrderIntent expresses the trade needed to move toward that target.
- Order remains the canonical OMS aggregate from milestone 0.2.

Strategy code never talks directly to a broker or ExecutionPort.

## Historical data and time

Milestone 0.4 introduces:

- Bar
- MarketDataEvent
- TimerEvent
- HistoricalDataset
- dataset identity, version, and SHA-256 checksum
- deterministic event ordering
- BacktestClock
- HistoricalMarketDataAdapter

The core temporal guarantee is:

~~~text
at time t
strategy sees only information <= t
~~~

The historical adapter exposes an event stream rather than a full future-indexable DataFrame.

BacktestClock advances only when the runtime processes a validated event. There is no implicit datetime.now() in strategy execution.

## Portfolio construction

TargetPosition can express:

- fixed quantity
- fixed notional
- percent NAV

RebalanceService computes:

~~~text
target position - current position = delta
~~~

and converts a non-zero delta into a canonical OrderIntent using ContractSpecification constraints.

## Simulated execution

SimulatedExecutionAdapter satisfies the same ExecutionPort used by OMS integrations.

P0 execution behavior:

~~~text
MARKET decided at close t
-> evaluated on the next eligible bar
-> filled at that bar open

BUY LIMIT
-> fill when future bar low <= limit

SELL LIMIT
-> fill when future bar high >= limit
~~~

Cost, slippage, and latency are explicit models recorded in RunManifest.

## Reproducibility

RunManifest captures at least:

- PyTradeKit version
- strategy identity and version
- strategy configuration hash
- dataset identity, version, and checksum
- risk-policy identity and version
- execution model
- cost model
- slippage model
- latency model
- random seed
- runtime profile
- deterministic start timestamp

The milestone qualifies the property:

~~~text
same code
+ same manifest
+ same dataset
+ same seed
= same semantic result
~~~

The Golden Backtest runs through Risk, OMS, simulated execution, Fill processing, and Portfolio accounting.

## Runnable examples

~~~bash
python examples/01_foundations.py
python examples/02_market_order_lifecycle.py
python examples/03_uncertain_submission_reconciliation.py
python examples/04_cancel_fill_race.py
python examples/05_portfolio_risk.py
python examples/06_strategy_backtest.py
~~~

## Package topology

~~~text
src/pytradekit/
├── shared/
├── reference/
├── orders/
├── execution/
├── portfolio/
├── risk/
├── strategy/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   ├── adapters/
│   └── portfolio_construction/
├── market_data/
│   └── domain/
├── backtesting/
│   ├── domain/
│   ├── application/
│   ├── adapters/
│   └── clock/
├── brokers/
├── runtime/
└── testing/
~~~

## Architecture protection

CI protects all earlier milestone boundaries plus 0.4-specific boundaries.

Important invariants include:

~~~text
Strategy domain does not depend on brokers
Strategy domain does not depend on backtesting adapters
Market-data domain does not depend on Strategy
Market-data domain does not depend on brokers
Backtest reuses canonical Risk
Backtest reuses canonical OMS
Backtest reuses canonical Fill
Backtest reuses canonical Portfolio
Package import graph remains acyclic
~~~

## Documentation

- Foundations architecture: docs/architecture/foundations.md
- OMS & Execution architecture: docs/architecture/oms-execution.md
- Portfolio & Risk architecture: docs/architecture/portfolio-risk.md
- Strategy & Backtest architecture: docs/architecture/strategy-backtest.md
- Strategy guide: docs/guides/strategy.md
- Backtesting guide: docs/guides/backtesting.md
- Portfolio guide: docs/guides/portfolio.md
- Risk guide: docs/guides/risk.md
- Testing guide: docs/guides/testing.md
- 0.4.0 release notes: docs/releases/0.4.0.md
- ADRs: docs/adr/

## Quality commands

~~~bash
make typography
make lint
make typecheck
make architecture
make test
make build
make release-check
make check
~~~

Release qualification validates version metadata, required 0.4 documentation, wheel and sdist builds, SHA-256 digests, clean wheel installation, installed-version identity, and every executable example.

## Explicit 0.4 scope boundaries

PyTradeKit 0.4 intentionally does not include:

- real broker connectivity
- durable database persistence
- restart recovery
- broker reconciliation
- corporate-action processing
- multi-currency FX conversion
- sophisticated exchange microstructure
- partial-fill simulation beyond the current P0 model
- HTTP API
- distributed workers
- production operations

These belong to later milestones.

## Critical path

~~~text
0.1 Foundations
-> 0.2 OMS & Execution
-> 0.3 Portfolio & Risk
-> 0.4 Strategy & Backtest
-> 0.5 Persistence + Alpaca Paper
-> 0.6 Reconciliation & Recovery
-> 0.7 Security & Operations
-> 0.8 Broker Compliance + IBKR
-> 0.9 Release Hardening
-> 1.0 Stable MVP
~~~

## Typography policy

Project-authored content uses the ASCII hyphen-minus character instead of the em dash character.

~~~bash
make typography
~~~

## License

PyTradeKit is licensed under the Apache License 2.0. See LICENSE for the full terms.
