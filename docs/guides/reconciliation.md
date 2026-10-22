# Reconciliation Guide

## When to reconcile

Use reconciliation whenever the runtime cannot prove that local economic state and broker state are aligned.

Typical triggers are startup, reconnect, uncertain submit, periodic verification, incident response, and manual investigation.

## Read the outcome

A ReconciliationRun exposes two independent dimensions:

~~~text
ConsistencyStatus
StateConfidence
~~~

Interpretation:

| Consistency | Confidence | Operational meaning |
| --- | --- | --- |
| CONSISTENT | HIGH | New risk may resume |
| CONSISTENT | MEDIUM | Restricted, policy dependent |
| DEGRADED | MEDIUM/LOW | Do not admit unrestricted new risk |
| INCONSISTENT | LOW | Block new risk and investigate |
| UNKNOWN | UNKNOWN | Fail closed |

## Manual workflow

The executable example is:

~~~bash
python examples/manual_reconciliation.py
~~~

It demonstrates a provider-neutral manual run over complete matching snapshots.

## Investigating mismatches

Start from the mismatch type and evidence, not from a guessed repair.

For Fill mismatches, stable provider execution identity is required before import.

For position or balance divergence, establish causality through orders, fills, external activity, and only then derived state.

Do not directly patch database rows as routine recovery.

## Stale evidence

If STALE_RECONCILIATION appears, do not retry the old correction.

Capture fresh snapshots and start a new run.

## External activity

UNKNOWN_EXTERNAL_ORDER and UNKNOWN_EXTERNAL_FILL are evidence that origin is not proven.

Do not attach them to a strategy or internal intent without lineage evidence.

## Verification

A resolution status of APPLIED is not sufficient.

The run must capture fresh snapshots, recompare them, and prove that the relevant mismatch no longer exists.

## Safe admission

New risk should consume ConsistencyAdmissionPolicy.

No reconciliation evidence is itself a blocking condition.

An active recovery workflow clears prior safe evidence before observation begins.
