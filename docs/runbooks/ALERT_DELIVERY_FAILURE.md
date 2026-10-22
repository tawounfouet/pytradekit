# Runbook - Alert Delivery Failure

## Trigger

An AlertSinkPort fails while routing an alert.

## Expected behavior

- the Alert remains OPEN or ACKNOWLEDGED in repository state;
- alert_delivery_failures_total increments;
- AlertDeliveryFailed operational event is emitted when possible;
- runtime economic state is unchanged.

## Operator actions

1. Inspect the open alert repository state first.
2. Restore the failed sink.
3. Verify delivery independently from alert state.
4. Do not resolve the original alert solely because delivery resumes.
5. Resolve only after the underlying condition is verified clear.
