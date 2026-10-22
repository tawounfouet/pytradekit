# Runbook - Broker Disconnected

## Trigger

BROKER_STREAM health becomes UNHEALTHY or stale beyond the configured threshold.

## Expected containment

- broker stream health is visible;
- BROKER_DISCONNECTED alert opens;
- readiness is recomputed;
- no false green health state is retained.

## Operator actions

1. Verify provider connectivity.
2. Verify read, command, stream, and market-data health separately.
3. Reconnect using the qualified recovery path.
4. Run reconciliation.
5. Confirm fresh consistency and confidence evidence.
6. Resolve the alert only after stream health is verified.

A stream reconnect alone does not manufacture trading readiness.
