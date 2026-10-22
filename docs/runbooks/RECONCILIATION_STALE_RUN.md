# Runbook - Stale Reconciliation Run

## Trigger

Use this runbook when a recovery run survives process failure or when the internal watermark changes before a planned correction.

## Stale correction

If the current internal watermark differs from the watermark used for comparison:

~~~text
do not apply old resolution
-> record STALE_RECONCILIATION
-> fail the run
-> start fresh reconciliation
~~~

## Abandoned active run

The single-process 0.6 runtime treats an active run older than the configured stale threshold as abandoned.

StaleRunRecovery marks that run FAILED before a fresh run starts.

## Restart after process kill

A prior economic repair may already have committed even if verification did not run.

The fresh run must recapture current durable state and must not replay an already processed external Fill.

## Exit

Resume only after the new run reaches CONSISTENT/HIGH.
