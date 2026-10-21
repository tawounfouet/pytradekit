# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit financial semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

PyTradeKit 0.1.x - Domain Foundations

PyTradeKit 0.1 provides the domain foundations only. It does not yet connect to brokers or execute trades.

The milestone provides canonical financial primitives, provider-independent instrument identity, explicit UTC time semantics, deterministic testing primitives, and mechanically enforced architecture boundaries.

## Requirements

- Python 3.12+
- no runtime dependencies for milestone 0.1

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
0.1.0
~~~

## First foundations example

~~~python
from decimal import Decimal

from pytradekit.shared import Currency, Price, Quantity

usd = Currency("USD")
price = Price(Decimal("192.50"), usd)
quantity = Quantity(Decimal("10"))

notional = price * quantity
print(notional)
~~~

Expected output:

~~~text
Money(1925.00 USD)
~~~

Run the complete example with:

~~~bash
python examples/01_foundations.py
~~~

## Package topology

~~~text
src/pytradekit/
├── shared/
├── reference/
│   └── domain/
├── runtime/
│   ├── ports/
│   └── adapters/
└── testing/
    ├── builders/
    └── strategies/
~~~

## Foundation capabilities

### Shared

- Currency
- Money
- Price
- Quantity
- Percentage
- InstrumentId and EventId
- CorrelationId and CausationId
- UTC datetime validation
- DomainEvent
- common domain errors

### Reference Data

- AssetClass
- canonical Instrument
- ContractSpecification
- InstrumentMapping

### Runtime and testing

- ClockPort
- SystemClock
- FakeClock
- InstrumentBuilder
- reusable Hypothesis finance strategies

### Architecture protection

CI enforces:

~~~text
FF-001 Domain has no infrastructure dependency
FF-002 Shared Kernel does not depend on bounded contexts
FF-003 Broker SDK imports are forbidden outside broker adapters
FF-004 No circular dependency
FF-005 Public root exports are controlled
~~~

## Documentation

- Foundations architecture: docs/architecture/foundations.md
- Financial Value Objects: docs/guides/value-objects.md
- Reference Data: docs/guides/reference-data.md
- Testing: docs/guides/testing.md
- 0.1.0 release notes: docs/releases/0.1.0.md
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

The release qualification builds wheel and sdist artifacts, calculates SHA-256 digests, installs the wheel in a clean virtual environment, imports the package, and runs the foundations example.

## Explicit 0.1 scope boundaries

PyTradeKit 0.1 intentionally does not include:

- OMS
- broker connectivity
- database persistence
- backtest engine
- HTTP API
- audit persistence
- runtime profiles

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

PyTradeKit is licensed under the Apache License 2.0. See `LICENSE` for the full terms.
