# PyTradeKit 0.8 IBKR Operational Runtime Runbook

## Purpose

This runbook covers LOT-06.6 dynamic market rules, pacing containment and reconnect recovery.

## Deterministic qualification

~~~bash
python scripts/qualify_ibkr_0_8_operations.py \
  --output artifacts/qualification/brokers/ibkr/operational-runtime.json
~~~

The gate validates:

~~~text
one reqMarketRule call site
dynamic LIMIT validation before placeOrder
ib_async throttling enabled
qualified request rate <= 45 requests/second
code 100 pacing latch
1100 / 1101 / 1102 / 1300 containment
2103 market-data-only degradation
reconnect -> reconciliation -> readmission
no Watchdog
no economic replay
~~~

## Dynamic LIMIT price incidents

### Missing market rule

Do not place the order.

Re-resolve ContractDetails and verify validExchanges and marketRuleIds positional alignment.

### Empty or malformed reqMarketRule response

Fail closed before placeOrder.

Do not fall back to reported minTick when marketRuleIds are present.

### Price outside active increment

Reject before economic write.

Use the increment active at the greatest lowEdge less than or equal to the candidate price.

## Pacing incidents

### throttleStart

Block new economic writes while ib_async is actively throttling its request queue.

### throttleEnd

Remove the temporary transport-throttle block.

### Provider code 100

Latch pacing containment.

Do not clear the latch merely because throttleEnd fired.

Call mark_pacing_recovered() only after the transport is no longer throttling and the operator or recovery workflow has established that request pressure is under control.

## Connectivity incidents

### 1100

Provider connectivity is lost.

Invalidate reconciliation readiness and block economic writes.

### 1101

Connectivity is restored but provider subscriptions are lost.

Require reconciliation before economic writes and explicit market-data resubscription before market-data admission.

### 1102

If reconciliation was already valid and no prior loss invalidated it, 1102 alone does not create a new reconciliation requirement.

If a prior 1100 or other containment event invalidated reconciliation, 1102 does not restore it.

### 1300

The socket port was reset and the connection dropped.

Perform explicit socket recovery. Do not replay any economic write.

### 2103

Degrade market-data admission only.

Do not globally block account or order operations solely because the market-data farm is disconnected.

### 2104

Mark market data healthy only when no explicit resubscription requirement remains.

## Explicit reconnect recovery

~~~text
unbind old provider events
-> stop old PAPER connection
-> reconnect through the qualified PAPER profile
-> verify startup
-> bind provider events
-> generic reconciliation
-> require CONSISTENT + HIGH
-> restore write admission
~~~

Connectivity recovery never invokes placeOrder or cancelOrder.

## Unknown provider states

Unknown or malformed provider operational events latch fail-closed state.

Do not reopen writes from an unknown state without explicit investigation and recovery.

## Production readiness

LOT-06.6 remains deterministic and provider-free in CI.

Real PAPER execution certification is still required before TRADING_READY can be opened for IBKR.
