# PyTradeKit

PyTradeKit is a domain-first, broker-agnostic trading framework designed around explicit domain semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

**PyTradeKit 0.1.x — Domain Foundations**

The 0.1 milestone establishes the canonical financial language and architectural foundations required by the future OMS, Portfolio/Risk, Backtest, and Broker Integration milestones.

> PyTradeKit 0.1 provides domain foundations only. It does not yet connect to brokers or execute trades.

## Architecture

PyTradeKit follows:

- Domain-Driven Design
- Hexagonal Architecture
- Ports & Adapters
- Modular Monolith
- Vertical-slice delivery

The initial core is intentionally infrastructure-free: no database, broker SDK, network dependency, or web framework.

## Requirements

- Python 3.12+

## Development status

The project is entering implementation with the following critical path:

```text
0.1 Foundations
→ 0.2 OMS & Execution
→ 0.3 Portfolio & Risk
→ 0.4 Strategy & Backtest
→ 0.5 Persistence + Alpaca Paper
→ 0.6 Reconciliation & Recovery
→ 0.7 Security & Operations
→ 0.8 Broker Compliance + IBKR
→ 0.9 Release Hardening
→ 1.0 Stable MVP
```

## License

A project license will be selected explicitly before the first public release.
