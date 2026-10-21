# PyTradeKit 0.2 - OMS & Execution Architecture

## Purpose

PyTradeKit 0.2 adds an Order Management System and a provider-neutral execution boundary on top of the 0.1 domain foundations.

The milestone is intentionally broker-agnostic. It proves order lifecycle semantics and fault behavior with a deterministic fake broker before any real venue is connected.

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

## Ownership

The Orders bounded context owns:

- OrderId
- OrderSide
- OrderType
- TimeInForce
- OrderStatus
- ExecutionCertainty
- Order aggregate
- order domain events and transition rules
- OrderRepository
- ExecutionPort
- SubmitOrder
- CancelOrder
- HandleExecutionReport
- ProcessFill
- GetOrder

The Execution domain owns provider-neutral external facts:

- Fill and FillId
- ExecutionReport
- ExecutionStatus
- SubmissionResult
- CancelResult

The broker adapter translates venue behavior into those canonical facts. The fake adapter is the only broker adapter in 0.2.

## Dependency direction

The critical direction is:

~~~text
orders.application -> orders.domain
orders.application -> orders.ports
orders.application -> execution.domain

orders.adapters -> orders.ports
brokers.adapters.fake -> orders.ports
brokers.adapters.fake -> execution.domain

orders.domain -> shared
execution.domain -> shared + OrderId
~~~

Forbidden architectural shortcuts include:

~~~text
orders.domain -> brokers
orders.domain -> execution
orders.domain -> broker SDK
shared -> orders
shared -> execution
~~~

The Order aggregate never invokes a broker.

## Order lifecycle

The canonical lifecycle includes:

~~~text
CREATED
  -> VALIDATED
  -> SUBMITTED
  -> ACCEPTED
  -> PARTIALLY_FILLED
  -> FILLED
~~~

Alternative terminal paths include:

~~~text
SUBMITTED -> REJECTED
ACCEPTED -> CANCEL_REQUESTED -> CANCELLED
ACTIVE -> EXPIRED
ACTIVE -> FAILED
~~~

A cancellation request is not equivalent to cancellation confirmation.

## Fill invariants

Each fill has a stable deduplication key.

Applying the same fill twice must produce one economic effect only.

The aggregate also enforces:

- filled quantity never exceeds order quantity
- FILLED requires filled quantity equal to order quantity
- a terminal state cannot regress because of a late transport message
- an external order id cannot silently change

## Uncertainty model

A timeout is not treated as a known failure.

The intended flow is:

~~~text
submit or cancel request
-> timeout
-> UNCERTAIN
-> no blind retry
-> query or reconciliation
-> canonical execution report
-> convergence
~~~

This prevents a transport failure from being interpreted as proof that the broker did not receive the command.

## Out-of-order reports

Execution reports are facts, not commands.

A fill may arrive before an acceptance report. The OMS accepts the economic fill and refuses to regress when the delayed acceptance later arrives.

Duplicate fills are ignored by identity.

A late cancellation confirmation cannot erase a full fill that already made the order FILLED.

## Persistence boundary

0.2 provides only InMemoryOrderRepository.

Database persistence, optimistic concurrency across processes, audit persistence, and restart recovery remain outside this milestone.

## Broker boundary

0.2 does not contain a real broker SDK.

FakeExecutionAdapter supports deterministic scenarios for:

- immediate acceptance
- immediate rejection
- immediate full fill
- partial fills followed by full fill
- uncertain submission with query resolution
- cancellation acceptance
- cancellation rejection
- cancellation timeout

The fake adapter is a qualification tool, not a production broker implementation.

## Mechanical qualification

CI protects the milestone with:

- Ruff
- strict mypy
- import-linter
- architecture tests
- unit tests
- property tests
- contract tests
- end-to-end tests
- fault and race tests
- clean wheel installation
- executable examples
- wheel and sdist SHA-256 qualification

## Explicit limitations

PyTradeKit 0.2 does not include:

- real broker connectivity
- durable database persistence
- restart reconciliation
- portfolio accounting
- risk engine
- strategy runtime
- backtest engine
- HTTP API
- distributed workers
- production operations
