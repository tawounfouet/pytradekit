# Changelog

All notable changes to PyTradeKit will be documented in this file.

The project is currently pre-1.0 and public APIs remain experimental unless explicitly documented otherwise.

## [Unreleased]

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