# Changelog

All notable changes to PyTradeKit will be documented in this file.

The project is currently pre-1.0 and public APIs remain experimental unless explicitly documented otherwise.

## [Unreleased]

## [0.1.0] - 2026-10-21

### Added

- Python 3.12+ package using a src layout.
- Financial Value Objects: Currency, Money, Price, Quantity, Percentage.
- Typed UUID identifiers for instruments and domain events.
- CorrelationId and CausationId.
- UTC-aware DomainEvent envelope.
- Canonical AssetClass and Instrument reference model.
- ContractSpecification for tick, step, quantity, and notional constraints.
- InstrumentMapping for provider-specific identifiers.
- ClockPort and SystemClock.
- Deterministic FakeClock.
- InstrumentBuilder and reusable Hypothesis finance strategies.
- Architecture fitness functions and import-linter contracts.
- Public import contract tests.
- Repository-wide typography guard.
- Foundations architecture, Value Object, Reference Data, and testing guides.
- Priority 0.1 architecture decision records.
- Executable foundations example.
- Release artifact qualification with clean wheel installation and SHA-256 output.

### Quality

- Ruff linting.
- strict mypy type checking.
- pytest unit tests.
- Hypothesis property tests.
- architecture and cycle tests.
- wheel and sdist build qualification.
- clean installation smoke test from the built wheel.
