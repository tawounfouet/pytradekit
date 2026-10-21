# ADR-003 - Hexagonal Architecture

## Status

Accepted for PyTradeKit 0.1.

## Decision

External capabilities are accessed through ports and implemented by adapters.

## Rationale

Trading domain logic must remain independent from broker SDKs, databases, web frameworks, and system-time access.

## Consequences

- Domain code depends on domain abstractions
- system time is exposed through ClockPort
- broker integrations will live behind future ports
- infrastructure types must not leak into canonical domain models
