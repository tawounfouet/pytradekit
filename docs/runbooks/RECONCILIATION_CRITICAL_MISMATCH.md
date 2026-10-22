# Runbook - Critical Mismatch

## Trigger

Use this runbook for CRITICAL divergence such as missing provider execution, order identity conflict, unknown external order, or position quantity divergence.

## Immediate safety

- Block risk-increasing commands.
- Suppress strategy target emission.
- Preserve all mismatch evidence.
- Do not force readiness.

## Position divergence

Position quantity mismatch is CRITICAL because actual exposure is not safely known.

Investigate in causal order:

~~~text
orders
-> fills
-> external activity
-> derived position
-> balance
~~~

Do not overwrite a position merely to match the broker snapshot.

## Exit

Only fresh reconciliation evidence can remove the block.

If causality remains unknown, keep the runtime INCONSISTENT or UNKNOWN and require manual review.
