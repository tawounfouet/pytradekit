# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit financial semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

PyTradeKit 0.8.0b1 - IBKR Anti-Corruption Layer

PyTradeKit 0.8 continues the Broker Compliance, Certification & IBKR milestone on top of the qualified 0.7 security and operations baseline.

LOT-05.1 introduces the first concrete IBKR Anti-Corruption Layer primitives. clientId, orderId, permId, orderRef, execId and conId now have explicit provider-local types and cannot silently replace canonical PyTradeKit identifiers.

Provider-neutral Broker models remain unchanged. No IBKR SDK dependency or provider network call is introduced yet. LIVE remains unavailable.

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
0.8.0b1
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
-> generic ReconciliationRun / Mismatch / Resolution
-> fresh verification
-> ConsistencyStatus + StateConfidence
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

## Startup, restart, and recovery

Runtime startup still executes the qualified 0.5 provider checks, then delegates final trading admission to the generic 0.6 reconciliation pipeline.

~~~text
load configuration
-> resolve secrets
-> verify PostgreSQL
-> verify PAPER account
-> load local durable state
-> load provider snapshots
-> 0.5 startup convergence
-> start authenticated trade_updates
-> second 0.5 convergence
-> generic 0.6 reconciliation
-> persist mismatches and resolutions
-> verify with fresh evidence
-> require CONSISTENT + HIGH
-> TRADING_READY
~~~

`READY_FOR_STARTUP` and `TRADING_READY` remain intentionally different states. New risk is blocked when reconciliation evidence is missing, degraded, inconsistent, unknown, or below HIGH confidence.

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

PyTradeKit 0.6 LOT-08 deterministic qualification additionally proves:

- clean startup reaches CONSISTENT/HIGH
- missing Fill recovery produces one canonical economic effect
- stale repair is rejected before side effects
- reconnect invalidates prior safe admission evidence
- partial snapshots cannot restore HIGH confidence
- durable-state outage fails closed before broker observation
- critical position divergence remains blocked
- uncertain submit converges by read-side evidence without resubmission
- process kill leaves a stale run that is closed on restart
- Outbox/commit failure rolls back the full recovery transaction
- FF-027 through FF-035 pass as architecture fitness functions
- 455 tests pass against PostgreSQL 16

Real Alpaca PAPER qualification from 0.5 additionally proved:

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
python examples/07_alpaca_paper_runtime.py
python examples/manual_reconciliation.py
~~~

The 0.5 example is safe by default. It performs no provider call, database
connection, or economic order unless explicitly opted in.

To exercise the real Alpaca PAPER startup, reconciliation, private stream, and
graceful shutdown path:

~~~bash
python examples/07_alpaca_paper_runtime.py --run-real-paper
~~~

The real path requires the `alpaca` and `postgres` extras plus the environment
documented in `docs/runbooks/PYTRADEKIT_0_5_RELEASE_QUALIFICATION.md`. It does
not submit or cancel broker orders.

The frozen 0.5 provider behavior can also be requalified manually through:

~~~text
.github/workflows/v050-real-paper.yml
~~~

That workflow intentionally uses `workflow_dispatch` only and checks out the
behavior candidate that originally passed the real Alpaca PAPER gate.

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
|-- reconciliation/
|-- brokers/
|   |-- compliance/
|   |-- adapters/alpaca/
|   `-- adapters/ibkr/
|-- runtime/
`-- testing/
~~~

## Architecture protection

Important invariants include:

~~~text
Domain does not depend on SQLAlchemy
Domain does not depend on broker SDKs
Alpaca SDK stays inside the adapter boundary
broker compliance core imports no concrete adapter
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
- Reconciliation architecture: docs/architecture/reconciliation.md
- Recovery architecture: docs/architecture/recovery.md
- Reconciliation guide: docs/guides/reconciliation.md
- 0.6 release qualification runbook: docs/runbooks/PYTRADEKIT_0_6_RELEASE_QUALIFICATION.md
- 0.6.0rc1 release notes: docs/releases/0.6.0rc1.md
- 0.6.0rc2 release notes: docs/releases/0.6.0rc2.md
- 0.6.0 Qualified Release notes: docs/releases/0.6.0.md
- Broker compliance architecture: docs/architecture/broker-compliance.md
- Broker certification guide: docs/guides/broker-certification.md
- Alpaca 0.8 compliance qualification: docs/qualification/alpaca-compliance-certification.md
- Alpaca 0.8 certification runbook: docs/runbooks/PYTRADEKIT_0_8_ALPACA_CERTIFICATION.md
- 0.8.0a1 release notes: docs/releases/0.8.0a1.md
- 0.8.0a2 release notes: docs/releases/0.8.0a2.md
- 0.8.0a3 release notes: docs/releases/0.8.0a3.md
- IBKR contract freeze: docs/architecture/ibkr-contract-freeze.md
- IBKR discovery guide: docs/guides/ibkr-discovery.md
- IBKR discovery qualification: docs/qualification/ibkr-discovery-contract-freeze.md
- 0.8.0a4 release notes: docs/releases/0.8.0a4.md
- IBKR provider identity architecture: docs/architecture/ibkr-identity-model.md
- 0.8.0b1 release notes: docs/releases/0.8.0b1.md
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

## Explicit 0.6.0 scope boundaries

PyTradeKit 0.6.0 intentionally does not include:

- LIVE trading
- IBKR or cTrader implementation
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
