# ADR-004 - Broker Anti-Corruption Layer

## Status

Accepted for PyTradeKit 0.5.

## Context

External trading providers expose incompatible concepts, identifiers, state machines, error taxonomies, numeric representations, and transport semantics.

Examples already observed:

```text
Alpaca client_order_id
Binance newClientOrderId
IBKR orderRef / orderId / permId
cTrader clientOrderId / orderId / dealId
```

Allowing provider SDK types to enter the Domain would make broker replacement require a domain rewrite.

## Decision

Every broker/provider integration MUST use an Anti-Corruption Layer:

```text
Provider SDK
    |
    v
Provider-specific ACL
    |
    +-- identity translation
    +-- Decimal conversion
    +-- state mapping
    +-- error translation
    +-- capability/constraint mapping
    |
    v
Provider-neutral PyTradeKit contracts
```

Provider SDK types are permitted only inside:

```text
pytradekit.brokers.adapters.<provider>
```

Canonical IDs are always supplied or created by PyTradeKit. Provider IDs are stored as external identities and never substituted for `OrderId`, `FillId`, `AccountId`, or `InstrumentId`.

Unknown or incomplete economic state is reconciled rather than guessed.

## Alpaca 0.5 application

The Alpaca ACL translates:

```text
Asset
TradeAccount
Position
Order
TradeUpdate
APIError
```

into:

```text
ProviderInstrumentSnapshot
ProviderAccountSnapshot
ProviderPositionSnapshot
ProviderOrderStateSnapshot
SubmissionResult
ExecutionReport
Fill
ProviderError hierarchy
```

A filled Alpaca `Order` snapshot does not contain an individual execution identity. Therefore the mapper MUST NOT fabricate a `Fill` from cumulative `filled_qty` and `filled_avg_price`. It requires execution reconciliation through `trade_updates` or an execution/fill recovery source.

## Consequences

Positive:

```text
Domain remains provider-neutral
numeric conversions are centralized
provider IDs stay external
error semantics are explicit
unknown outcomes remain safe
future providers can reuse broker boundary models
```

Costs:

```text
more mapping code
contract tests required
provider schema changes become explicit maintenance events
```

## Fitness functions

```text
FF-022 Alpaca SDK confined to Alpaca adapter
FF-026 provider IDs cannot replace canonical IDs
no float conversion for economic truth
filled order snapshots cannot fabricate execution IDs
provider-neutral broker models import no provider SDK
```
