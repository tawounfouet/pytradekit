# Runbook - Broker Disconnect

## Trigger

Use this runbook after provider transport disconnect, WebSocket reconnect, or a provider read failure during reconciliation.

## Immediate safety

Entering reconnect recovery invalidates prior admission evidence.

Transport reconnect alone must never restore TRADING_READY.

## Procedure

1. Keep new risk blocked.
2. Re-establish transport connectivity.
3. Capture fresh broker orders, fills, positions and balances.
4. Capture fresh internal durable state.
5. Run reconciliation with trigger RECONNECT.
6. Resolve only supported evidence-backed mismatches.
7. Verify from fresh snapshots.
8. Resume only on CONSISTENT/HIGH.

## Failure mode

If broker snapshot capture fails, RecoveryState becomes FAILED and the old safe evidence remains invalid.

Run a fresh reconnect reconciliation when provider reads are healthy again.
