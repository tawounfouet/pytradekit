# Reconciliation Architecture

## Purpose

PyTradeKit 0.6 treats uncertainty as explicit domain state.

The reconciliation bounded context answers one question:

~~~text
Can current internal economic state be proven consistent with external broker facts?
~~~

The answer is evidence based. It is never inferred from transport success, process liveness, or the absence of an exception.

## Core pipeline

~~~text
trigger
-> create ReconciliationRun
-> establish a comparison cut
-> capture InternalSnapshot
-> capture BrokerSnapshot
-> validate completeness
-> compare canonical facts
-> persist Mismatch evidence
-> plan explicit Resolution records
-> apply only evidence-backed recovery
-> capture fresh verification snapshots
-> compare again
-> compute ConsistencyStatus + StateConfidence
-> publish admission evidence
~~~

A completed run does not imply consistency.

## Domain ownership

The reconciliation domain owns:

- ReconciliationRun and its lifecycle
- canonical snapshots and watermarks
- mismatch taxonomy and severity
- resolution planning and verification state
- ConsistencyStatus
- StateConfidence
- RecoveryPlan and RecoveryState

It does not own broker commands, ORM mutation, portfolio accounting rules, order lifecycle rules, or authorization policy.

## Canonical snapshots

InternalSnapshot represents durable PyTradeKit facts.

BrokerSnapshot represents normalized provider observations.

Both use provider-neutral structures:

- CanonicalOrder
- CanonicalFill
- CanonicalPosition
- CanonicalBalance

Provider SDK objects are normalized at adapter boundaries.

## Completeness

Snapshot completeness is explicit:

~~~text
COMPLETE
PARTIAL
UNKNOWN
~~~

UNKNOWN cannot produce HIGH confidence.

PARTIAL cannot prove unrestricted consistency.

COMPLETE is necessary for HIGH confidence but is not sufficient by itself.

## Watermarks and stale protection

Every internal snapshot carries an economic watermark.

A recovery action may execute only if the durable internal watermark still matches the watermark used by the original comparison.

~~~text
compare at watermark A
-> internal state moves to B
-> old recovery action rejected
-> STALE_RECONCILIATION
-> fresh reconciliation required
~~~

This prevents a stale correction from overwriting newer economic truth.

## Deterministic comparison

OrderComparator, FillComparator, PositionComparator, BalanceComparator and SnapshotComparator are pure comparison services.

P0 economic comparisons use Decimal semantics and explicit canonical identity. Arbitrary float epsilon is not used.

Mismatch identities are deterministic for a run and economic entity.

## Critical economic divergence

A position quantity divergence is CRITICAL because actual exposure is not safely known.

Unresolved CRITICAL evidence cannot produce CONSISTENT.

## Persistence

PostgreSQL stores:

~~~text
reconciliation.runs
reconciliation.mismatches
reconciliation.resolutions
~~~

Evidence is checkpointed during a run so process failure does not erase already observed uncertainty.

Run state uses optimistic concurrency. Active ownership prevents overlapping reconciliation from silently mutating the same account scope.

## Verification rule

Applying a resolution is not convergence.

~~~text
APPLIED
!=
VERIFIED
~~~

A resolution is VERIFIED only from fresh evidence captured strictly after the recovery effect.

A planned symptom resolution can be closed as REJECTED with superseded_by_fresh_convergence when a causal repair removes that symptom before any action was executed.

## Safety integration

The only unrestricted admission state is:

~~~text
ConsistencyStatus.CONSISTENT
+
StateConfidence.HIGH
~~~

This evidence is consumed by TradingReadiness, SubmitOrder and StrategyRuntime.

All other states fail closed for new risk.
