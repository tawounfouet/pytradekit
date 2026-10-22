# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit financial semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

PyTradeKit 0.5.0 - Persistence + Alpaca PAPER

PyTradeKit 0.5 adds the first durable provider-connected PAPER runtime while preserving the Risk, OMS, Fill, Portfolio, Strategy, and Backtest core delivered by earlier milestones.

The Alpaca integration is PAPER-only. LIVE trading is not available or qualified in 0.5.

## Requirements

- Python 3.12+
- optional PostgreSQL dependencies through the `postgres` extra
- optional Alpaca dependencies through the `alpaca` extra
- development tooling through the `dev` extra

## Development setup

~~~bash
git clone https://github.com/tawounfouet/pytradekit.git
cd pytradekit

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,postgres,alpaca]"

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
0.5.0
~~~

## Milestone flow

~~~text
Canonical Order
-> Risk
-> durable PostgreSQL state
-> Runtime Admission Gate
-> ExecutionPort
-> AlpacaExecutionAdapter
-> Alpaca PAPER
-> private trade_updates
-> Inbox
-> Alpaca ACL
-> ExecutionReport / Fill
-> OMS + Portfolio
-> Outbox
-> PostgreSQL commit
-> restart reconciliation
-> TRADING_READY
~~~

## Persistence

0.5 introduces durable PostgreSQL infrastructure:

- SQLAlchemy adapters
- Alembic migrations
- context-owned repositories
- PostgresUnitOfWork
- transactional Inbox
- transactional Outbox
- ProcessedFillRegistry
- optimistic concurrency

The provider call is not hidden inside a long database transaction.

## Alpaca PAPER safety

The 0.5 provider contract is intentionally narrow:

~~~text
provider          Alpaca
environment       PAPER
sdk               alpaca-py==0.44.0
asset scope       US_EQUITY
order types       MARKET / LIMIT
time in force     DAY
market data       IEX
LIVE              unavailable
~~~

Safety invariants include:

~~~text
no blind retry of economic writes
one explicit submit/cancel transport attempt
UNCERTAIN instead of guessed failure
client_order_id recovery
provider IDs remain external
no synthetic Fill
unknown divergence blocks TRADING_READY
~~~

## Startup and restart

Runtime startup uses durable local state plus provider observations.

~~~text
load configuration
-> resolve secrets
-> verify PostgreSQL
-> verify PAPER account
-> load local durable state
-> load provider snapshots
-> reconcile
-> start authenticated trade_updates
-> reconcile again
-> TRADING_READY
~~~

`READY_FOR_STARTUP` and `TRADING_READY` are intentionally different states.

## Runtime lifecycle

0.5 provides:

~~~text
STARTING
READY
DEGRADED
DRAINING
STOPPED
~~~

During DRAINING:

- new submits are blocked
- cancellation and query paths remain available while safe
- shutdown waits for bounded active work
- forced shutdown remains observable

## Qualification

0.5 separates deterministic integration qualification from real provider qualification.

Deterministic qualification covers:

- PostgreSQL restart convergence
- duplicate provider events
- pre-commit crash rollback
- post-commit replay idempotency
- 429 / 5xx write uncertainty
- graceful shutdown
- architecture and typing gates
- package artifact qualification

Real Alpaca PAPER qualification additionally proved:

- MARKET execution
- LIMIT submission
- CANCEL
- private trade_updates
- simulated post-ack response loss
- recovery by client_order_id without resubmission
- cleanup to the baseline position
- full runtime start, stop, rebuild, and restart

## Backtest and strategy

The 0.4 Strategy & Backtest Runtime remains part of the framework.

PyTradeKit keeps:

~~~text
Signal
!= TargetPosition
!= OrderIntent
!= Order
~~~

Backtest uses the same Risk, OMS, Fill, and Portfolio semantics as other execution environments.

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
|-- shared/
|-- reference/
|-- orders/
|-- execution/
|-- portfolio/
|-- risk/
|-- strategy/
|-- market_data/
|-- backtesting/
|-- persistence/
|-- brokers/
|   `-- adapters/alpaca/
|-- runtime/
`-- testing/
~~~

## Architecture protection

Important invariants include:

~~~text
Domain does not depend on SQLAlchemy
Domain does not depend on broker SDKs
Alpaca SDK stays inside the adapter boundary
provider IDs never replace canonical IDs
Strategy domain does not depend on brokers
Backtest reuses canonical Risk
Backtest reuses canonical OMS
Backtest reuses canonical Fill
Backtest reuses canonical Portfolio
package import graph remains acyclic
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
- 0.5 release qualification runbook: docs/runbooks/PYTRADEKIT_0_5_RELEASE_QUALIFICATION.md
- Alpaca PAPER incident runbook: docs/runbooks/ALPACA_PAPER_INCIDENT_RESPONSE.md
- 0.5.0 release notes: docs/releases/0.5.0.md
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

Release qualification validates version metadata, release notes, changelog state, README version state, wheel and sdist builds, SHA-256 digests, clean wheel installation, installed-version identity, and executable examples.

## Explicit 0.5 scope boundaries

PyTradeKit 0.5 intentionally does not include:

- LIVE trading
- IBKR or cTrader implementation
- a generic ReconciliationRun / Mismatch / Resolution domain
- generic Missing Fill Recovery
- external manual activity classification
- distributed workers
- leases or fencing
- full RBAC
- production kill switch
- HTTP API stabilization
- multi-account allocation
- advanced derivatives

These belong to later milestones.

## Critical path

~~~text
0.1 Foundations
-> 0.2 OMS & Execution
-> 0.3 Portfolio & Risk
-> 0.4 Strategy & Backtest
-> 0.5 Persistence + Alpaca PAPER
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
