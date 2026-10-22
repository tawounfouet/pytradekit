# Changelog

All notable changes to PyTradeKit will be documented in this file.

The project is currently pre-1.0 and public APIs remain experimental unless explicitly documented otherwise.

## [Unreleased]

## [0.7.0a2] - 2026-10-22

### Added

- LOT-02 Authorization & Scoped Permissions.
- AuthorizationDecision, AuthorizationPolicy, AuthorizationService, and stable reason codes.
- PrincipalProvider and authorization audit ports.
- Explicit SUBMIT_ORDER and CANCEL_ORDER authorization before economic side effects.
- Negative and property tests for missing permissions, disabled actors, expired assignments, and scope mismatch.
- E2E proof that denied order actions never reach ExecutionPort.

### Safety

- SubmitOrder and CancelOrder require an explicit OrderAuthorizationGatePort.
- Orders depends on a consumer-owned authorization port and does not import Security directly.
- Missing account context fails closed on sensitive order actions.
- LIVE remains unavailable.

## [0.7.0a1] - 2026-10-22

### Added

- LOT-01 Identity, Actors & RBAC.
- Typed ActorId, ActorType, Actor, RoleId, Role, Permission, and PermissionSet.
- AuthenticatedPrincipal and PrincipalContext.
- Typed environment, account, and operation authorization scopes.
- Time-bound RoleAssignment with deterministic expiry.
- In-memory and PostgreSQL security repositories.
- Alembic security schema migration.
- FF-036 provider independence for security.domain.

### Safety

- Security domain is provider-neutral and SQLAlchemy-independent.
- Actor contains no password or secret.
- Scope wildcard semantics use typed values rather than magic strings.
- LIVE remains unavailable.


## [0.6.0] - 2026-10-22

### Qualified Release

- Reconciliation & Recovery is qualified from domain foundations through failure recovery and fresh convergence verification.
- LOT-01 through LOT-08 are complete.
- 455 tests pass against PostgreSQL 16 on the final rc2 qualification candidate.
- FF-027 through FF-035 pass and protect provider independence, infrastructure boundaries, canonical recovery paths, safety admission, and stale-repair ordering.
- Missing Fill recovery, duplicate replay, stale repair, partial snapshots, reconnect, durable-state outage, uncertain submit, process kill, and Outbox transaction failure are qualified.
- Recovery invalidates old admission evidence before observation and restores unrestricted risk only from fresh CONSISTENT/HIGH evidence.
- Release publication is hardened to run the complete deterministic quality gate with PostgreSQL before creating a new GitHub tag.
- Reconciliation architecture, Recovery architecture, guide, incident runbooks, qualification runbook, and manual reconciliation example are mandatory release artifacts.

### Compatibility

- Python 3.12+.
- Alpaca remains PAPER-only and pinned to alpaca-py==0.44.0.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.
- Distributed leases/fencing, full RBAC, production kill switch, advanced alert routing, and LIVE qualification move to later milestones.

## [0.6.0rc2] - 2026-10-22

### Added

- LOT-08 end-to-end reconciliation and recovery qualification matrix.
- Deterministic reconciliation fault windows for capture, comparison, resolution, verification, and completion.
- Recovery containment that invalidates prior safe admission evidence before reconnect, incident, periodic, or submit-uncertainty reconciliation.
- Explicit process-kill recovery qualification with stale-run closure and no duplicate economic repair.
- Transactional Outbox failure qualification proving full rollback before safe replay.
- Stale watermark qualification proving that an old correction is rejected before any recovery side effect.
- Reconciliation and Recovery architecture documentation, operational guide, five incident runbooks, release qualification runbook, and executable manual reconciliation example.
- Complete FF-027 through FF-035 architecture fitness-function coverage.

### Safety

- Position quantity divergence is CRITICAL and cannot restore unrestricted trading.
- Planned symptom resolutions that disappear after a causal repair are closed as REJECTED by fresh convergence evidence instead of remaining unresolved.
- Any recovery workflow clears old CONSISTENT/HIGH admission evidence before observing new state.
- A broker reconnect does not restore readiness without fresh reconciliation.
- A durable-state outage fails before provider observation and leaves risk admission closed.
- Partial snapshots cannot produce HIGH confidence.
- Unknown external orders remain explicit and require manual review.
- Missing Fill recovery remains exactly-once at the canonical economic-effect level.
- Process death after a durable repair but before verification cannot cause duplicate repair on restart.
- Outbox/commit failure rolls back Fill, OMS, Portfolio, ProcessedFillRegistry, and Outbox changes atomically.

### Qualification

- 455 tests pass against PostgreSQL 16.
- 87 architecture and public-import tests pass.
- 34 production-fault qualification tests pass.
- Ruff, strict mypy, Import Linter, typography, architecture, property, integration, E2E, qualification, and release-artifact gates pass.
- The release artifact qualifier requires Reconciliation/Recovery architecture docs, operational runbooks, and the manual reconciliation example.
- Behavior candidate before rc2 metadata: e2bb8e24854f775731742c40a7408439debaa2a1.

### Compatibility

- Python 3.12+.
- Alpaca remains PAPER-only and pinned to alpaca-py==0.44.0.
- 0.6.0rc2 is the final qualification candidate before the 0.6.0 Qualified Release.
- Distributed leases/fencing, full RBAC, production kill switch, advanced alerts, and LIVE qualification remain outside 0.6.

## [0.6.0rc1] - 2026-10-22

### Added

- First-class reconciliation domain with typed run, mismatch, resolution, scope, trigger, recovery, consistency, confidence, completeness, and watermark semantics.
- Deterministic canonical order, fill, position, and balance snapshot comparators.
- PostgreSQL reconciliation evidence schema with durable runs, mismatches, resolutions, optimistic concurrency, stale-run queries, and explicit checkpoints.
- Generic account, order, fill, position, and balance reconciliation use cases with mandatory fresh verification.
- Alpaca account activity reader for stable FILL execution facts without synthesizing fills from cumulative order quantities.
- Missing Fill recovery through the canonical Fill, OMS, Portfolio, ProcessedFillRegistry, and Outbox path.
- External activity classification that preserves unknown provider origin instead of silently internalizing it.
- Recovery workflows for STARTUP, PERIODIC, RECONNECT, SUBMIT_UNCERTAINTY, INCIDENT, and MANUAL triggers.
- Concrete PostgreSQL internal snapshot and Alpaca broker snapshot adapters.
- Generic 0.6 reconciliation gate integrated after the qualified 0.5 Alpaca PAPER startup baseline.
- Consistency and confidence admission gates for TradingReadinessReport, SubmitOrder, and StrategyRuntime target emission.

### Safety

- Reconciliation domain remains provider-independent and persistence-independent.
- Snapshot comparison is deterministic and uses exact Decimal semantics for P0 economic facts.
- Unknown or incomplete evidence cannot produce HIGH-confidence consistency.
- Missing external fills are imported only from stable provider execution identities.
- The same external fill is qualified to produce one canonical economic effect and one import Outbox event.
- External orders with unproven origin remain explicit and require review.
- Recovery evidence is checkpointed durably during the run instead of only at final completion.
- Economic correction is blocked when the internal watermark changes before mutation.
- Resolution verification requires evidence strictly newer than the applied recovery effect.
- New risk is fail-closed unless reconciliation proves CONSISTENT + HIGH.
- Strategy target emission is suppressed when consistency admission is unsafe.
- Alpaca remains PAPER-only with no LIVE fallback.

### Qualification

- Ruff, strict mypy, Import Linter, architecture contracts, public import checks, and production fault qualification pass.
- 434 unit, property, integration, architecture, contract, E2E, and qualification tests pass against PostgreSQL 16.
- Missing Fill recovery idempotence is qualified against real PostgreSQL transactions.
- Generic Alpaca startup reconciliation is mechanically required after the 0.5 startup baseline.
- Typography policy remains enforced repository-wide.

### Compatibility

- Python 3.12+.
- Alpaca integration contract remains pinned to alpaca-py==0.44.0.
- 0.6.0rc1 is a release candidate and does not declare the 0.6 stable API complete.
- Existing Risk, OMS, Fill, Portfolio, Strategy, Backtest, Persistence, and Alpaca PAPER semantics remain in place.


## [0.5.0] - 2026-10-22

### Added

- PostgreSQL persistence with SQLAlchemy, Alembic migrations, context-owned repositories, and optimistic concurrency.
- PostgresUnitOfWork with transactional Inbox, Outbox, and ProcessedFillRegistry semantics.
- Provider discovery and comparative architecture across Alpaca, Binance Spot, IBKR, and Pepperstone with cTrader.
- Alpaca PAPER RuntimeProfile, ProviderManifest, SecretsPort, environment-backed secret resolution, and explicit composition root.
- Alpaca anti-corruption layer for provider identities, errors, order states, account snapshots, position snapshots, and instrument/reference data.
- AlpacaExecutionAdapter implementing MARKET, LIMIT, CANCEL, and order-query operations through the canonical ExecutionPort.
- IEX latest quotes and canonical asset, account, and position snapshot integration.
- Authenticated Alpaca private trade_updates processing through transactional Inbox, OMS, Portfolio, ProcessedFillRegistry, and Outbox handling.
- Startup and restart reconciliation with remote open-order inventory, account and position convergence checks, two-pass stream reconciliation, and TradingReadinessReport.
- Runtime admission control, graceful shutdown, SIGTERM and SIGINT handling, deterministic fault injection, runtime metrics, and structured operational events.
- Real Alpaca PAPER qualification harness and explicit v0.5.0 release gate.

### Safety

- Alpaca integration is PAPER-only with no LIVE fallback.
- Economic provider writes use one explicit transport attempt with SDK automatic retries disabled.
- Unknown write outcomes become UNCERTAIN and are reconciled instead of blindly retried.
- client_order_id is used for uncertain submission recovery.
- Provider IDs remain external evidence and never replace canonical PyTradeKit IDs.
- Cumulative provider order fields never fabricate canonical Fill records.
- Unknown remote orders or portfolio divergence block TRADING_READY.
- Pre-commit crash windows roll back atomically and post-commit replay is idempotent.
- New risk-increasing submissions require runtime readiness.

### Qualification

- Deterministic CI run 39789341350 passed on candidate a7768911b56bb25a7efd24aae12f3cb032a5c9ef.
- Real Alpaca PAPER qualification run 39789766678 passed all required gates.
- Controlled PAPER qualification executed MARKET, LIMIT, CANCEL, private trade_updates, uncertain recovery, cleanup, graceful stop, and fresh runtime restart.
- The simulated post-ack response-loss scenario recovered by client_order_id with one submit attempt and no resubmission.
- PAPER qualification observed nine private trade_updates and restored the AAPL position to its zero baseline.
- Sanitized qualification artifact 12430172671 recorded release_ready=true.

### Compatibility

- Python 3.12+.
- Alpaca integration contract pinned to alpaca-py==0.44.0.
- Alpaca scope is US equities, MARKET and LIMIT orders, DAY time in force, IEX market data, and PAPER only.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.

## [0.4.0] - 2026-10-22

### Added

- StrategyId, StrategyVersion, StrategyRunId, StrategyRunStatus, StrategyRun, and explicit StrategyState.
- StrategyProtocol and StrategyRuntime for deterministic market-data and timer callbacks.
- Signal, TargetPosition, OrderIntent, and StrategyRequirements with explicit semantic separation.
- Bar, MarketDataEvent, TimerEvent, HistoricalDataset, DataQuality, and canonical dataset checksums.
- BacktestClock as a deterministic ClockPort implementation controlled only by the runtime.
- HistoricalMarketDataAdapter with dataset checksum, ordering, range, interval, and duplicate validation.
- FixedQuantitySizing, FixedNotionalSizing, PercentNAVSizing, and RebalanceService.
- ExecutionModel, CostModel, SlippageModel, LatencyModel, and SimulatedExecutionAdapter.
- Next-eligible-bar MARKET execution and deterministic LIMIT fill rules.
- RunBacktest orchestration through the existing Risk, OMS, ExecutionReport, Fill, and Portfolio core.
- BacktestRun, BacktestRunId, RunManifest, BacktestReport, BacktestMetrics, and equity-curve capture.
- Deterministic strategy-run, backtest-run, order, correlation, and fill identities derived from run semantics.
- Golden Backtest qualification with deterministic replay and fixed expected economics.
- Strategy and Backtest architecture guide, Strategy guide, Backtesting guide, and executable release example.

### Quality

- Strategy domain remains broker independent and cannot import backtesting adapters.
- Market-data domain remains strategy and broker independent.
- historical data is validated before iteration and no future row access surface is exposed to strategy code.
- BacktestClock cannot move backwards and does not depend on wall-clock time.
- simulated execution implements the canonical ExecutionPort instead of a backtest-specific OMS.
- Risk, OMS, Fill, and Portfolio semantics are reused unchanged in backtests.
- Golden Backtest qualifies same-manifest deterministic replay.
- strict mypy, Ruff, Import Linter, architecture tests, contracts, unit tests, property tests, E2E tests, and release artifact qualification pass together.
- release qualification validates version metadata, 0.4 documentation, release notes, changelog state, README version state, wheel, sdist, SHA-256 output, clean installation, and all executable examples.

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