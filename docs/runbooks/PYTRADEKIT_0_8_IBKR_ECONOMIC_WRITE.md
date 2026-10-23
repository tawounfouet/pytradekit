# PyTradeKit 0.8 IBKR Economic Write Runbook

## Purpose

This runbook covers LOT-06.5 economic-write behavior.

The implementation contains real placeOrder and cancelOrder call sites, but CI does not send provider orders.

## Qualification

~~~bash
python scripts/qualify_ibkr_0_8_execution.py \
  --output artifacts/qualification/brokers/ibkr/economic-write-execution.json
~~~

The qualification validates one placeOrder call site, one cancelOrder call site, no automatic retry, explicit admission, permId external identity and the dynamic LIMIT guard.

## Submission incidents

### placeOrder raises

Treat as UNCERTAIN. Do not submit again.

Reconcile using orderRef, clientId, reserved orderId, openOrder, orderStatus and execDetails.

### placeOrder returns permId = 0

Treat as UNCERTAIN. Wait for callback or reconcile. Do not use orderId as external_order_id.

### Trade payload identity mismatch

Treat as UNCERTAIN. The economic write has already been attempted. Do not retry.

## Cancellation incidents

### cancelOrder raises

Treat as UNCERTAIN. Do not issue another cancel blindly.

### Trade unavailable

Do not guess the provider order object. Return UNCERTAIN and reconcile.

## LIMIT orders

Static tick LIMIT orders are eligible when LOT-05.3 validation passes.

Dynamic market-rule LIMIT orders remain blocked in LOT-06.5.

Do not bypass this guard by using minTick as a universal tick.

## Production readiness

LOT-06.5 does not open TRADING_READY. Real PAPER certification is still required.
