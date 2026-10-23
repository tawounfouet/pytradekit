# Changelog

All notable changes to PyTradeKit will be documented in this file.

The project is currently pre-1.0 and public APIs remain experimental unless explicitly documented otherwise.

## [Unreleased]

## [0.8.0b1] - 2026-10-23

### Added

- LOT-05.2 IBKR Contract & Instrument Mapping.
- SDK-free IBKRContractRecord and IBKRContractDetailsRecord.
- IBKRInstrumentMappingResult retaining provider-only contract metadata.
- conId to ProviderInstrumentIdentity and InstrumentMapping conversion.
- STK/SMART/USD mapping to canonical EQUITY Instrument.
- minSize and sizeIncrement mapping to ContractSpecification.
- marketRuleIds-aware price increment handling that avoids false static tick-size claims.
- Dedicated LOT-05.2 architecture, public-contract, unit and qualification gates.
- LOT-05.1 IBKR Provider Primitives & Identity Model.
- IBKRClientId, IBKRSessionOrderId, IBKRPermanentOrderId and IBKROrderReference.
- IBKRExecutionId and explicit IBKRExecutionCorrection relationship.
- IBKRContractId and IBKRContractIdentity.
- IBKRConnectionIdentity and IBKROrderIdentity.
- Conflict-safe IBKROrderIdentityRegistry.
- Explicit conversions to existing ProviderOrderIdentity, ProviderFillIdentity and ProviderInstrumentIdentity.
- Dedicated architecture, public-contract, unit and qualification tests.
- Machine-readable LOT-05.1 qualification artifact.

### Architecture

- orderId remains session-local and never becomes external_order_id.
- ProviderOrderIdentity requires a non-zero permId.
- orderRef remains a provider correlation reference.
- execId identifies provider execution observations without creating Fill semantics.
- conId remains provider instrument identity.
- clientId remains provider runtime identity.
- Generic broker identity models remain IBKR-free.
- No ibapi or ib_async dependency is introduced.

### Compatibility

- BrokerAdapterContract remains candidate version 1.0-rc1.
- LOT-04 contract freeze remains valid.
- No IBKR PAPER certification claim is made.
- LIVE remains unavailable.
- LOT-05.2 Contract & Instrument Mapping is implemented.
- LOT-05.3 Order Command Mapping remains next.

## [0.8.0a4] - 2026-10-23

### Added

- LOT-04 IBKR Discovery & Contract Freeze.
- Dependency-free IBKR discovery package with a machine-readable contract freeze.
- PAPER and LIVE socket port matrix with fail-closed PAPER validation.
- Frozen identity semantics for orderRef, orderId, permId, execId, conId and clientId.
- IBKR readiness facts including nextValidId and reconciliation completion.
- Target and deferred capability inventory for the first US-equity PAPER vertical slice.
- Reconnect policy requiring implicit resubmission to remain disabled.
- Canonical contract compatibility decisions and explicit unresolved PAPER questions.
- IBKR architecture, discovery, qualification and release documentation.
- Dedicated LOT-04 CI qualification gate.

### Architecture

- ExecutionPort and BrokerSnapshotPort remain unchanged.
- ProviderOrderIdentity maps client_reference to orderRef and external_order_id to permId.
- ProviderFillIdentity maps external_fill_id to execId.
- ProviderInstrumentIdentity maps external_id to conId.
- orderId, clientId and nextValidId remain adapter-local runtime state.
- The Alpaca-only RuntimeProfile is not extended with IBKR provider branches.
- No IBKR-specific logic enters Domain, OMS, Risk, Portfolio, Reconciliation or Safety.

### Dependency policy

- Official TWS API 10.49+ is documented by IBKR as GPL.
- PyTradeKit remains Apache-2.0.
- Official ibapi is not added pending explicit license review.
- ib_async remains a candidate implementation and is not added by LOT-04.

### Qualification

- PAPER port 4002 and TWS PAPER port 7497 are accepted only for their explicit surfaces.
- LIVE ports 4001 and 7496 are rejected.
- No IBKR CertifiedCapability is emitted.
- Unresolved PAPER behavior remains an explicit blocker to later certification.
- LIVE remains unavailable.

### Compatibility

- BrokerAdapterContract remains candidate version 1.0-rc1.
- Alpaca 0.8.0a3 certification remains unchanged.
- IBKR ACL implementation is deferred to LOT-05.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.

## [0.8.0a3] - 2026-10-23

### Added

- LOT-03 Alpaca Compliance Certification.
- Alpaca ProviderCapabilityManifest mapping for the frozen PAPER adapter.
- Capability-specific Alpaca C2/C3 requirements and scenarios.
- Normalized retained real PAPER evidence with GitHub Actions provenance and SHA-256 linkage.
- AlpacaComplianceScenarioExecutor and retained-evidence fixture.
- Alpaca CertifiedCapability generation through the common ComplianceHarness.
- Capability matrix with C3 for real PAPER-proven capabilities and C2 for PARTIAL_FILL.
- Dedicated Alpaca 0.8 qualification report and runbook.
- Manual v0.8.0a3 real PAPER requalification workflow.
- Dedicated LOT-03 CI qualification gate.

### Qualification

- Real Alpaca PAPER evidence comes from workflow run 39789766678 and artifact 12430172671.
- MARKET, LIMIT, CANCEL, queries, client reference, execution facts, recovery, account, balance, position and IEX quote evidence are replayed through the common compliance harness.
- PARTIAL_FILL remains C2 because the retained real provider artifact contains no genuine partial_fill event.
- Adapter version changes invalidate retained certification.
- No fake PAPER evidence is promoted to C3.
- LIVE remains unavailable.

### Compatibility

- BrokerAdapterContract remains candidate version 1.0-rc1.
- The frozen Alpaca adapter remains behavior-compatible with the qualified 0.5 scope.
- IBKR discovery and contract freeze remain deferred to LOT-04.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.

## [0.8.0a2] - 2026-10-23

### Added

- LOT-02 Compliance Test Kit & Evidence Model.
- ComplianceRequirement, ComplianceScenario, ComplianceResult and explicit PASS/FAIL/BLOCKED/NOT_APPLICABLE semantics.
- ComplianceEvidence linked to exact commit, provider, environment, adapter, SDK, contract and scenario.
- EvidenceSanitizer with secret-key, authorization-marker and caller-supplied sensitive-value redaction.
- ComplianceHarness using the same ProviderFixture surface for every provider.
- ComplianceReport, ComplianceReportGenerator and deterministic ComplianceRun JSON artifacts.
- CertifiedCapability and immutable generated CertificationRegistry.
- StaleEvidencePolicy for adapter, SDK, contract, commit and age invalidation.
- ProviderCapabilityManifest schema candidate version 1.0-rc1.
- Broker certification guide.
- FF-057 through FF-059.

### Qualification

- C3 requirements require PAPER evidence.
- BLOCKED and FAIL remain distinct.
- Cleanup failure blocks qualification.
- Common fake ProviderFixture implementations pass through the same harness without provider branching.
- Stale evidence cannot remain current after an adapter version change.
- Complete qualification artifacts are secret-scanned.
- Raw SDK objects are rejected from evidence payloads.

### Compatibility

- BrokerAdapterContract remains candidate version 1.0-rc1.
- Alpaca provider certification is deferred to LOT-03.
- IBKR implementation is not introduced.
- LIVE remains unavailable.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.

## [0.8.0a1] - 2026-10-23

### Added

- LOT-01 Broker Adapter Contract Candidate.
- BrokerCapability taxonomy with P0 and optional capabilities.
- CapabilityConstraint and CapabilitySupport for capability-scoped applicability.
- CertificationLevel from C0 DEFINED through C5 LIVE QUALIFIED.
- ProviderCapabilityManifest as a declaration model distinct from certification evidence.
- BrokerAdapterContract v1 candidate with version 1.0-rc1.
- ProviderFixture protocol reusing canonical ExecutionPort and BrokerSnapshotPort.
- Broker compliance architecture documentation.
- FF-048 through FF-056 broker-neutrality architecture fitness functions.
- Import Linter boundary protecting the compliance core from concrete provider adapters.

### Architecture

- Existing runtime ProviderManifest remains intact for the frozen Alpaca 0.5 contract.
- ProviderCapabilityManifest does not certify a provider capability.
- Domain, OMS, Risk, Portfolio, Reconciliation and Safety remain free of concrete provider branching.
- Provider IDs remain external evidence rather than canonical identity.
- No new provider-specific ExecutionPort or reconciliation core is introduced.

### Compatibility

- Python 3.12+.
- Alpaca remains PAPER-only and pinned to alpaca-py==0.44.0.
- IBKR implementation is deferred to later 0.8 LOTs.
- LIVE remains unavailable.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.

## [0.7.0] - 2026-10-22

### Stable Qualified Release

- Security, Governance & Production Operations milestone completed through LOT-08.
- Identity, Actors & RBAC qualified.
- Scoped authorization and negative provider-reachability proofs qualified.
- SafetyState, SafetyDecision and SafetyGate qualified.
- KillSwitch and RiskOverride governance qualified with durable PostgreSQL state.
- Health, liveness, operational readiness, metrics, tracing and stateful alerting qualified.
- Secrets and single-node deployment hardening qualified.
- Adversarial production qualification promoted from 0.7.0rc2 without functional scope expansion.
- 563 tests pass on the stable release candidate, with dedicated 0.7 production qualification, architecture, fault, deployment and artifact gates.
- PostgreSQL stale governance writers are rejected through optimistic concurrency.
- Release artifacts are rebuilt, clean-installed and smoke-tested before publication.

### Safety

- Unauthorized sensitive actions cannot reach the execution provider.
- Safety-denied actions cannot reach the execution provider.
- KillSwitch cannot be bypassed by RiskOverride.
- UNKNOWN and INCONSISTENT economic truth cannot be overridden.
- Expired RiskOverride cannot bypass configured risk policy.
- Critical health failures close unsafe admission.
- Alert sink and telemetry failures cannot corrupt economic state.
- Secret-provider failures fail closed without leaking credential material.
- LIVE remains unavailable by design.

### Compatibility

- Python 3.12+.
- Alpaca remains PAPER-only and pinned to alpaca-py==0.44.0.
- Production-like deployment baseline remains single-node.
- Public APIs remain pre-1.0 and experimental unless explicitly documented otherwise.

## [0.7.0rc2] - 2026-10-22

### Added

- LOT-08 Production Qualification & Release.
- Dedicated 0.7 production qualification CI and Release gates.
- Negative authorization qualification for permission, account, environment and expired-role failures.
- Cross-cutting KillSwitch, RiskOverride and hard-safety release-blocker tests.
- Real PostgreSQL restart and optimistic-concurrency qualification for governance state.
- Release-blocker evidence manifest and final 0.7 qualification matrix.
- Operational runbooks for authorization denial, KillSwitch, RiskOverride, critical mismatch and trading-readiness loss.

### Qualification

- Unauthorized sensitive actions cannot reach the execution provider.
- Safety-denied actions cannot reach the execution provider.
- KillSwitch dominates RiskOverride.
- UNKNOWN and INCONSISTENT economic truth cannot be overridden.
- Expired RiskOverride cannot bypass risk policy.
- Persisted KillSwitch survives process restart.
- Stale PostgreSQL governance writers are rejected.
- Critical health, alerting, telemetry and secret-outage scenarios are replayed in the release gate.
- LIVE remains unavailable.

## [0.7.0rc1] - 2026-10-22

### Added

- LOT-07 Secrets & Deployment Hardening.
- FileSecrets, ExternalSecretsProvider, RoutedSecrets, and configurable SecretRef values.
- RuntimeSecurityConfig for bounded lifecycle, PostgreSQL TLS, timeouts, and pool controls.
- Explicit Alpaca PAPER endpoint validation.
- Deployment preflight and read-only container health endpoints.
- Migration-before-runtime container entrypoint with SecretRef-backed Alembic database URL.
- Provider outage, rotation, and startup timeout runbooks.
- Single-node deployment qualification and FF-047.

### Safety

- Missing required references fail closed before broker infrastructure construction.
- Provider errors are sanitized.
- Configuration stores references rather than credential values.
- Startup timeout cannot create late admission.
- Telemetry flush failure cannot prevent STOPPED state.
- LIVE remains unavailable.


## [0.7.0b2] - 2026-10-22

### Added

- LOT-06 Metrics, Tracing & Alerting.
- Low-cardinality labeled metrics on the existing RuntimeMetrics registry.
- Authorization, safety, health, readiness, alert, and telemetry failure metrics.
- TraceContext and TraceRecord preserving CorrelationId and CausationId.
- TraceRecorder with exporter fault isolation.
- OpenTelemetry-compatible trace adapter without a core OpenTelemetry dependency.
- AlertId, AlertType, AlertSeverity, AlertState, and stateful Alert lifecycle.
- AlertRepositoryPort, AlertRouterPort, AlertSinkPort, and TraceExporterPort.
- Alert deduplication, acknowledgement, verified resolution, and health-condition evaluation.
- In-memory alert state, runtime event sink, and deterministic failing sink for qualification.

### Safety

- Metric labels reject high-cardinality identifiers.
- Secret-like telemetry field names and values are rejected.
- Alert state is stored before sink delivery is attempted.
- Alert sink failure retains the unresolved alert and records delivery failure metrics.
- Telemetry exporter failure cannot alter application operation results.
- OpenTelemetry remains an adapter, not a core dependency.
- LIVE remains unavailable.


## [0.7.0b1] - 2026-10-22

### Added

- LOT-05 Health, Liveness & Operational Readiness.
- HealthStatus, HealthComponent, HealthReport, HealthSnapshot, and HealthRegistry.
- Per-component freshness policies that expire stale HEALTHY evidence.
- LivenessStatus independent from external dependency health.
- OperationalReadinessReport preserving existing TradingReadinessReport authority.
- Read-only dependency health checks for database, broker APIs, streams, market data, outbox, inbox, reconciliation, and runtime.
- Health-aware SafetyEvidence projection for critical dependencies.
- Application operations for health, liveness, readiness, monitoring, and admission reflection.

### Safety

- Liveness is distinct from operational readiness.
- Operational readiness is distinct from trading readiness.
- Critical database, broker command, or runtime health loss closes unsafe admission.
- Health code does not mutate trading aggregates.
- Stale HEALTHY evidence becomes UNKNOWN by policy.
- LIVE remains unavailable.


## [0.7.0a4] - 2026-10-22

### Added

- LOT-04 Kill Switch & Risk Overrides.
- Persistent KillSwitch with GLOBAL, ENVIRONMENT, ACCOUNT, and STRATEGY scopes.
- Governed activation and stricter release flow.
- Time-bound RiskOverride request, approval, creation, and revocation semantics.
- DangerousActionConfirmation with bounded expiry and process-bound restart behavior.
- PostgreSQL safety governance persistence with optimistic concurrency.
- Runtime safety audit adapter reusing the existing observer surface.
- Order and strategy KillSwitch integration.

### Safety

- KillSwitch blocks risk-increasing submits and strategy targets.
- KillSwitch never performs an implicit flatten.
- RiskOverride expires deterministically.
- RiskOverride cannot bypass KillSwitch, UNKNOWN, INCONSISTENT, low confidence, or authorization.
- KillSwitch release requires authorization, explicit confirmation, and safe underlying evidence.
- Dangerous actions emit audit evidence.
- LIVE remains unavailable.

## [0.7.0a3] - 2026-10-22

### Added

- LOT-03 SafetyState & SafetyDecision.
- Explicit SafetyState, SafetyAction, SafetyReason, SafetyDecision, SafetyPolicy, and SafetyGate.
- ConsistencyStatus, StateConfidence, RecoveryState, RuntimeLifecycleState, trading readiness, and risk integration.
- Orders-owned safety port for submit and cancel.
- Strategy admission adapter backed by SafetyGate.
- Explicit safety reason codes and order result evidence.

### Safety

- Authorization allow does not imply safety allow.
- UNKNOWN and INCONSISTENT economic truth block risk increase.
- Risk reduction is based on projected portfolio semantics, never BUY/SELL heuristics.
- Cancel and reconciliation policies remain explicit in restricted states.
- LIVE remains unavailable.


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