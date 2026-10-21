# PyTradeKit 0.1 - Foundations Architecture

## Purpose

PyTradeKit 0.1 establishes the canonical financial language and architecture required by later OMS, Portfolio, Risk, Strategy, Backtest, and Broker Integration milestones.

PyTradeKit 0.1 provides the domain foundations only. It does not yet connect to brokers or execute trades.

## Architectural style

PyTradeKit 0.1 follows:

- Domain-Driven Design
- Hexagonal Architecture
- Ports & Adapters
- Modular Monolith
- Vertical-slice delivery

The domain model is built before infrastructure integrations.

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

## Shared Kernel

pytradekit.shared contains only cross-context primitives:

- Currency
- Money
- Price
- Quantity
- Percentage
- typed UUID identifiers
- correlation and causation identifiers
- UTC datetime validation
- DomainEvent
- common domain errors

It cannot depend on bounded contexts, runtime adapters, testing helpers, or broker integrations.

## Reference Data

pytradekit.reference owns canonical instrument reference data:

- AssetClass
- Instrument
- ContractSpecification
- InstrumentMapping

InstrumentId is the canonical identity. Provider symbols and provider identifiers are mappings, not domain identity.

## Runtime

pytradekit.runtime currently contains the clock boundary:

~~~text
ClockPort
   ^
   |
SystemClock
~~~

The Domain does not call the system clock implicitly.

## Testing

pytradekit.testing contains deterministic test support:

- FakeClock
- InstrumentBuilder
- reusable Hypothesis finance strategies

Testing helpers are not domain dependencies.

## Dependency rules

Allowed:

~~~text
reference.domain -> shared
runtime.adapters -> runtime.ports
testing -> public/domain test targets
~~~

Forbidden:

~~~text
shared -> reference
shared -> runtime
shared -> testing
reference.domain -> runtime
reference.domain -> testing
runtime.ports -> runtime.adapters
domain -> broker SDK
domain -> SQLAlchemy
domain -> FastAPI
~~~

These boundaries are enforced by import-linter and architecture tests.

## Financial representation

Financial values use Decimal as their canonical representation.

float is not accepted silently by Money, Price, Quantity, or Percentage.

No global rounding policy is encoded in the Shared Kernel. Venue and contract constraints belong to ContractSpecification.

## Time policy

Critical domain timestamps must be timezone-aware and UTC.

The Domain does not normalize non-UTC timestamps silently and does not call datetime.now() as a hidden dependency.

## Event policy

DomainEvent carries EventId, UTC-aware occurred_at, CorrelationId, optional CausationId, and event_version.

Integration events are outside milestone 0.1.

## Architecture fitness functions

CI protects:

~~~text
FF-001 Domain has no infrastructure dependency
FF-002 Shared Kernel does not depend on bounded contexts
FF-003 Broker SDK imports are forbidden outside broker adapters
FF-004 No circular dependency
FF-005 Public root exports are controlled
~~~

## Root API policy

During milestone 0.1, the package root exposes only __version__. Domain types remain available from their explicit package surfaces.

## Out of scope

The following are intentionally absent from 0.1:

- database
- OMS
- broker adapter
- backtest engine
- HTTP API
- audit persistence
- runtime profiles

These are scope boundaries, not accidental omissions.
