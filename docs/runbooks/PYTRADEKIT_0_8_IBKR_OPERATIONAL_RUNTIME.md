# PyTradeKit 0.8 IBKR Operational Runtime Runbook

## Purpose

This runbook covers LOT-06.6 pacing, connectivity recovery and dynamic market-rule handling.

## Code 100

Treat as provider pacing containment.

~~~text
code 100
-> latch pacing violation
-> block economic writes
-> no retry
~~~

After transport throttling has ended and operator/runtime evidence is safe, call mark_pacing_recovered().

## Code 1100

Provider connectivity is lost.

Block writes and market data. Reconciliation is required after restoration.

## Code 1101

Connectivity is restored but provider data subscriptions were lost.

Run reconciliation before economic writes resume.

Keep market-data admission closed until subscriptions are explicitly restored.

## Code 1102

Connectivity is restored with provider data maintained.

If a prior loss invalidated reconciliation, run reconciliation before writes resume.

Do not replay placeOrder or cancelOrder.

## Code 1300

The API socket port was reset.

Perform explicit socket reconnect, startup validation, event rebind and reconciliation.

## Code 2103

Treat as market-data degradation only.

Do not globally block account/order reads or economic writes solely because of 2103.

## Dynamic LIMIT

Resolve the routing marketRuleId and reqMarketRule before placeOrder.

If the rule is unavailable or the LIMIT price violates the active increment, reject before economic write.

## Qualification

~~~bash
python scripts/qualify_ibkr_0_8_operations.py \
  --output artifacts/qualification/brokers/ibkr/operational-runtime.json
~~~

## Certification

LOT-06.6 does not produce real PAPER evidence and does not open TRADING_READY.
