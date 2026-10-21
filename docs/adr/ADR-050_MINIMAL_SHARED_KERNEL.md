# ADR-050 - Minimal Shared Kernel

## Status

Accepted for PyTradeKit 0.1.

## Decision

The Shared Kernel contains only concepts that are genuinely cross-context and stable enough to be reused broadly.

## Rationale

A large shared package creates hidden coupling and makes bounded contexts harder to evolve independently.

## Consequences

The Shared Kernel contains primitives such as Currency, Money, Price, Quantity, Percentage, typed IDs, correlation primitives, and DomainEvent.

It cannot depend on Reference Data, runtime adapters, testing helpers, or broker integrations.
