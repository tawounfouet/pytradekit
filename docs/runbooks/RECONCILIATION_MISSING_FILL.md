# Runbook - Missing Fill

## Trigger

Use this runbook when broker execution history contains a Fill that is absent from durable PyTradeKit state.

## Immediate safety

- Block new risk through reconciliation containment.
- Do not synthesize a Fill from cumulative filled quantity or average price.
- Preserve the provider execution identifier.

## Procedure

1. Capture a fresh internal snapshot.
2. Capture broker execution history.
3. Confirm a stable external fill identity.
4. Confirm the execution maps to a canonical order.
5. Record MISSING_INTERNAL_FILL.
6. Plan IMPORT_MISSING_EXTERNAL_EVENT.
7. Apply through PostgresResolutionExecutor and the normal ProcessFill path.
8. Capture fresh verification snapshots.
9. Require the mismatch to disappear.
10. Require CONSISTENT/HIGH before unrestricted trading resumes.

## Success evidence

- exactly one canonical Fill exists for the external execution
- exactly one portfolio economic effect occurred
- one ProcessedFillRegistry key exists
- one ExternalFillImported Outbox event exists
- the resolution is VERIFIED
- final reconciliation is CONSISTENT/HIGH

## Escalation

If execution identity is unavailable or order lineage cannot be proven, stop automatic recovery and require manual review.
