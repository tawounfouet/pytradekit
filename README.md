# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit financial semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

PyTradeKit 0.3.0 - Portfolio & Risk

PyTradeKit 0.3 gives canonical economic meaning to execution fills and adds a deterministic pre-trade risk boundary before broker submission.

The milestone still uses a deterministic fake broker. It does not connect to a real broker or submit live trades.

## Requirements

- Python 3.12+
- no runtime dependencies for milestone 0.3

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

On Windows PowerShell, activate the virtual environment with:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

## Version

~~~bash
pytradekit --version
~~~

Current release version:

~~~text
0.3.0
~~~

## Quick Portfolio and Risk model

~~~python
from decimal import Decimal

from pytradekit.portfolio.domain import AccountId
from pytradekit.risk.domain import RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.risk.domain.rules import MaxOrderSize
from pytradekit.shared import Currency, Money

USD = Currency("USD")
account_id = AccountId.new()

policy = RiskPolicy(
    id=RiskPolicyId.new(),
    name="global-order-limit",
    scope=RiskScope.GLOBAL,
    limits=(MaxOrderSize(Money(Decimal("10000"), USD)),),
    enabled=True,
    version=1,
)
~~~

Complete runnable examples:

~~~bash
python examples/01_foundations.py
python examples/02_market_order_lifecycle.py
python examples/03_uncertain_submission_reconciliation.py
python examples/04_cancel_fill_race.py
python examples/05_portfolio_risk.py
~~~

## Package topology

~~~text
src/pytradekit/
├── shared/
├── reference/
├── orders/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   └── adapters/
├── execution/
│   └── domain/
├── portfolio/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   └── adapters/
├── risk/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   └── adapters/
├── brokers/
│   └── adapters/
│       └── fake/
├── runtime/
└── testing/
~~~

## Portfolio capabilities

### Portfolio domain

- AccountId
- Account
- Balance
- Position
- PositionSide
- signed position quantity
- weighted average entry price
- partial close
- full close
- long-to-short flip
- short-to-long flip
- realized PnL
- duplicate-fill economic protection

### Valuation

- PositionView
- PortfolioSnapshot
- market value
- NAV
- realized PnL
- unrealized PnL
- gross exposure
- net exposure
- leverage

### Application

- ApplyFillToPortfolio
- BuildPortfolioSnapshot

## Risk capabilities

### Risk domain

- RiskPolicyId
- RiskPolicy
- RiskLimit
- RiskScope
- RiskDecision
- RiskEvaluation
- RiskViolation
- RiskOrder
- RiskContext
- ProjectedPortfolio

### P0 rules

- MaxOrderSize
- MaxPositionSize
- MaxGrossExposure
- MaxLeverage
- DailyLoss

### Trading halt

- TradingHaltId
- TradingHalt
- GLOBAL scope
- ACCOUNT scope
- STRATEGY scope
- explicit trigger
- explicit release
- reduce-only behavior

## Pre-trade safety flow

~~~text
SubmitOrderCommand
-> canonical Order
-> projected portfolio
-> risk policies and limits
-> ALLOW / WARN / REJECT / HALT
-> ExecutionPort only when allowed
~~~

Risk projection never mutates actual Position or Balance state.

A REJECT decision returns before ExecutionPort.submit.

A MARKET order requires explicit reference pricing for risk evaluation.

A LIMIT order uses its limit price.

Missing required state fails safe for risk-increasing activity.

## Fill accounting flow

~~~text
ExecutionReport
-> Fill
-> ProcessFill
-> Order
-> PortfolioEffectPort
-> ApplyFillToPortfolio
-> Position + Balance
~~~

Duplicate fills have one Portfolio economic effect only.

## Architecture protection

CI enforces the original 0.1 and 0.2 boundaries plus milestone 0.3 boundaries.

Important fitness functions include:

~~~text
Portfolio domain does not depend on Risk
Portfolio domain does not depend on brokers
Risk domain does not depend on brokers
Orders domain does not depend on Risk
Portfolio and Risk domains do not depend on persistence frameworks
Package import graph has no cycles
Public root exports remain controlled
~~~

## Documentation

- Foundations architecture: docs/architecture/foundations.md
- OMS & Execution architecture: docs/architecture/oms-execution.md
- Portfolio & Risk architecture: docs/architecture/portfolio-risk.md
- Financial Value Objects: docs/guides/value-objects.md
- Reference Data: docs/guides/reference-data.md
- Orders: docs/guides/orders.md
- Portfolio: docs/guides/portfolio.md
- Risk: docs/guides/risk.md
- Fake Execution: docs/guides/fake-execution.md
- Testing: docs/guides/testing.md
- 0.3.0 release notes: docs/releases/0.3.0.md
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

The release qualification validates version metadata, builds wheel and sdist artifacts, calculates SHA-256 digests, installs the wheel in a clean virtual environment, verifies the installed version, and runs every executable example.

## Explicit 0.3 scope boundaries

PyTradeKit 0.3 intentionally does not include:

- real broker connectivity
- durable database persistence
- restart recovery
- broker reconciliation
- strategy runtime
- backtest runtime
- multi-currency FX conversion
- HTTP API
- distributed workers
- production operations

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

The repository enforces this rule with:

~~~bash
make typography
~~~

## License

PyTradeKit is licensed under the Apache License 2.0. See LICENSE for the full terms.
