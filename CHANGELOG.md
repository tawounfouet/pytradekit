# Changelog

All notable changes to PyTradeKit will be documented in this file.

The project is currently pre-1.0 and public APIs remain experimental unless explicitly documented otherwise.

## [Unreleased]

## [0.3.0] - 2026-10-22

### Added

- AccountId, Account, Balance, Position, and PositionSide portfolio primitives.
- Signed position accounting with weighted average price, partial closes, full closes, and position flips.
- Realized PnL, cash accounting, fee accounting, and duplicate-fill economic protection.
- PortfolioSnapshot and PositionView immutable read models.
- NAV, realized and unrealized PnL, gross exposure, net exposure, and leverage calculations.
- BuildPortfolioSnapshot application service.
- RiskPolicyId, RiskPolicy, RiskLimit, RiskScope, RiskDecision, RiskEvaluation, RiskViolation, RiskOrder, and RiskContext.
- ProjectedPortfolio for deterministic pre-trade hypothetical state.
- MaxOrderSize, MaxPositionSize, MaxGrossExposure, MaxLeverage, and DailyLoss P0 risk rules.
- TradingHalt and TradingHaltId with GLOBAL, ACCOUNT, and STRATEGY scopes.
- Explicit halt trigger and release use cases with reduce-only behavior.
- PortfolioViewPort, PositionRepository, BalanceRepository, ProcessedFillRegistry, RiskPolicyRepository, and TradingHaltRepository.
- Consumer-owned RiskEvaluationPort and PortfolioEffectPort for Orders integration.
- OrdersRiskEvaluationAdapter and OrdersPortfolioEffectAdapter.
- Fill -> Portfolio integration through ProcessFill and HandleExecutionReport.
- Projected Risk -> SubmitOrder gate with broker-call prevention on rejection.
- Portfolio and Risk architecture fitness functions and repository contract tests.
- Portfolio accounting property tests.
- Portfolio/Risk end-to-end qualification tests.
- Portfolio & Risk architecture guide and Portfolio/Risk usage guides.
- Executable Portfolio/Risk release example.

### Quality

- risk rejection is mechanically qualified to avoid any ExecutionPort.submit call.
- duplicate fills are mechanically qualified as one Portfolio economic effect.
- signed position accounting is qualified across arbitrary fill sequences.
- trading halt reduce-only behavior is qualified.
- strict mypy, Ruff, Import Linter, architecture tests, contracts, unit tests, property tests, and E2E tests pass together.
- release qualification validates version metadata, release notes, changelog state, README version state, wheel, sdist, SHA-256 output, clean installation, and all executable examples.
- GitHub Release title is derived from the versioned release notes rather than hard-coded to a milestone name.

## [0.2.0] - 2026-10-21

### Added

- Order primitives: OrderId, OrderSide, OrderType, TimeInForce, OrderStatus, ExecutionCertainty.
- Order aggregate with explicit lifecycle transitions, invariants, events, and errors.
- Canonical Fill, FillId, ExecutionReport, ExecutionStatus, SubmissionResult, and CancelResult.
- Consumer-owned ExecutionPort and OrderRepository.
- InMemoryOrderRepository.
- Deterministic FakeExecutionAdapter and FakeExecutionScenario.
- SubmitOrder, CancelOrder, HandleExecutionReport, ProcessFill, and GetOrder use cases.
- Immutable OrderSnapshot read DTO.
- Stable fill deduplication semantics.
- Submission and cancellation uncertainty semantics without blind retry.
- Query-based convergence for uncertain submission.
- Out-of-order acceptance protection.
- Cancel/fill race handling.
- End-to-end OMS qualification tests.
- Fault and race qualification tests.
- OMS & Execution architecture guide.
- Orders and Fake Execution guides.
- Executable market-order, uncertainty, and cancel/fill race examples.

### Quality

- 0.2 E2E scenarios run in the normal pytest suite.
- duplicate fills are mechanically qualified as one economic effect.
- terminal-state monotonicity is mechanically qualified.
- timeout uncertainty is mechanically qualified.
- cancellation uncertainty blocks blind resubmission.
- wheel qualification runs all executable examples in a clean virtual environment.
- GitHub Release workflow re-runs release qualification before publishing artifacts.
- wheel, sdist, and SHA256SUMS are attached to the versioned GitHub Release.

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
