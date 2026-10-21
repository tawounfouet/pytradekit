# ADR-048 - Domain-First Package Topology

## Status

Accepted for PyTradeKit 0.1.

## Decision

Package organization follows domain responsibilities before infrastructure technologies.

## Rationale

The primary design vocabulary is financial and trading semantics, not persistence, HTTP, or vendor SDKs.

## Consequences

- canonical financial primitives live in pytradekit.shared
- instrument reference data lives in pytradekit.reference
- runtime boundaries live in pytradekit.runtime
- testing support lives in pytradekit.testing
- infrastructure packages cannot become the organizing center of the codebase
