# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit financial semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

PyTradeKit 0.2.0 - OMS & Execution

PyTradeKit 0.2 adds a canonical Order Management System and a provider-neutral execution boundary on top of the 0.1 domain foundations.

The milestone deliberately uses a deterministic fake broker. It does not connect to a real broker or submit live trades.

## Requirements

- Python 3.12+
- no runtime dependencies for milestone 0.2

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
0.2.0
~~~

## Quick OMS example

~~~python
from decimal import Decimal

from pytradekit.orders import OrderSide, OrderType, TimeInForce
from pytradekit.orders.application import SubmitOrderCommand
from pytradekit.shared import CorrelationId, InstrumentId, Quantity

command = SubmitOrderCommand(
    instrument_id=InstrumentId.new(),
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=Quantity(Decimal("10")),
    time_in_force=TimeInForce.DAY,
    correlation_id=CorrelationId.new(),
)
~~~

Complete runnable examples:

~~~bash
python examples/01_foundations.py
python examples/02_market_order_lifecycle.py
python examples/03_uncertain_submission_reconciliation.py
python examples/04_cancel_fill_race.py
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
├── brokers/
│   └── adapters/
│       └── fake/
├── runtime/
└── testing/
~~~

## OMS capabilities

### Orders domain

- OrderId
- OrderSide
- OrderType
- TimeInForce
- OrderStatus
- ExecutionCertainty
- Order aggregate
- explicit transitions and domain events
- fill deduplication
- overfill protection
- terminal-state monotonicity

### Execution domain

- Fill and FillId
- ExecutionReport
- ExecutionStatus
- SubmissionResult
- CancelResult

### Application

- SubmitOrder
- CancelOrder
- HandleExecutionReport
- ProcessFill
- GetOrder
- OrderSnapshot

### Ports and adapters

- ExecutionPort
- OrderRepository
- InMemoryOrderRepository
- FakeExecutionAdapter
- FakeExecutionScenario
- FakeClock

## Failure semantics

A timeout is not a rejection.

PyTradeKit 0.2 uses the following policy:

~~~text
request
-> timeout
-> UNCERTAIN
-> no blind retry
-> query or reconciliation
-> canonical execution report
-> convergence
~~~

Duplicate fills have one economic effect only.

A late acceptance cannot regress a partially filled or filled order.

A full fill wins over a later cancellation confirmation.

## Architecture protection

CI enforces:

~~~text
FF-001 Domain has no infrastructure dependency
FF-002 Shared Kernel does not depend on bounded contexts
FF-003 Broker SDK imports are forbidden outside broker adapters
FF-004 No circular dependency
FF-005 Public root exports are controlled
FF-006 Orders domain does not depend on brokers or execution
FF-007 Execution domain does not depend on brokers
~~~

## Documentation

- Foundations architecture: docs/architecture/foundations.md
- OMS & Execution architecture: docs/architecture/oms-execution.md
- Financial Value Objects: docs/guides/value-objects.md
- Reference Data: docs/guides/reference-data.md
- Orders: docs/guides/orders.md
- Fake Execution: docs/guides/fake-execution.md
- Testing: docs/guides/testing.md
- 0.2.0 release notes: docs/releases/0.2.0.md
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

The release qualification builds wheel and sdist artifacts, calculates SHA-256 digests, installs the wheel in a clean virtual environment, imports the package, verifies the declared version, and runs every executable example.

## Explicit 0.2 scope boundaries

PyTradeKit 0.2 intentionally does not include:

- real broker connectivity
- database persistence
- restart recovery
- portfolio accounting
- risk engine
- strategy runtime
- backtest engine
- HTTP API
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
