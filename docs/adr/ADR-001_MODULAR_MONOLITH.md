# ADR-001 - Modular Monolith

## Status

Accepted for PyTradeKit 0.1.

## Decision

PyTradeKit begins as a modular monolith with explicit bounded package surfaces and dependency rules.

## Rationale

The framework needs strong domain boundaries without the operational complexity of distributed services during the foundations milestone.

A single package keeps testing and refactoring inexpensive while architecture fitness functions protect module boundaries.

## Consequences

- modules remain explicit
- cross-module dependencies are mechanically checked
- distributed deployment is deferred
- later extraction remains possible if operational needs justify it
