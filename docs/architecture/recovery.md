# Recovery Architecture

## Principle

Recovery converts uncertainty into verified knowledge.

~~~text
unknown
-> contain risk
-> observe
-> reconcile
-> resolve
-> verify
-> prove convergence
-> resume only when allowed
~~~

Transport recovery and economic recovery are separate.

A WebSocket reconnect does not prove that no execution event was missed.

## Recovery states

RecoveryState is separate from the process lifecycle:

~~~text
IDLE
CONTAINING
OBSERVING
RECONCILING
RESOLVING
VERIFYING
RECOVERED
BLOCKED
FAILED
~~~

Entering a recovery workflow invalidates prior admission evidence immediately.

This means an old CONSISTENT/HIGH result cannot keep the risk gate open during reconnect, incident handling, submit uncertainty, or periodic recovery.

## Operational triggers

The generic pipeline supports:

- STARTUP
- PERIODIC
- RECONNECT
- SUBMIT_UNCERTAINTY
- INCIDENT
- MANUAL
- POST_DEPLOYMENT

All triggers converge through ReconcileAccount rather than provider-specific repair logic.

## Missing Fill recovery

A provider execution can be imported automatically only when stable evidence exists.

~~~text
stable provider execution id
+
canonical order mapping
+
canonical quantity, price, currency, timestamp
-> canonical Fill
-> ProcessFill
-> OMS
-> Portfolio
-> ProcessedFillRegistry
-> Outbox
-> commit
-> fresh verification
~~~

Cumulative broker order fields never fabricate individual Fill records.

## External activity

Unknown external activity is preserved as unknown.

An unmapped provider order does not silently become an internal strategy order.

Unknown origin leads to explicit classification, blocking evidence, and manual review unless a safe import rule can prove the economic fact and lineage.

## Transactional recovery

Missing Fill import uses the normal UnitOfWork.

Fill persistence, OMS mutation, Portfolio mutation, ProcessedFillRegistry and Outbox are committed atomically.

If commit fails, all local economic changes rollback together.

Replay is safe because provider execution identity and processed-fill identity are stable.

## Crash recovery

Reconciliation evidence is checkpointed before economic repair.

A process kill can therefore leave an active durable run.

On restart:

~~~text
find stale active run
-> mark abandoned run FAILED
-> start a fresh run
-> recapture current durable state
-> recapture broker truth
-> verify whether prior economic repair already committed
-> never repeat an already processed Fill effect
~~~

## No blind economic retry

Provider submit and cancel remain single-attempt economic writes.

Unknown write outcome becomes uncertainty and is resolved by read-side evidence or reconciliation.

Read operations may use bounded retry when provider semantics make that safe.

## Resume rule

RecoveryState.RECOVERED is not set merely because a resolution executor returned.

The workflow resumes unrestricted risk only when a completed run proves CONSISTENT/HIGH.
