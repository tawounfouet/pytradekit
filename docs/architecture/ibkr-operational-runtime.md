# IBKR Operational Runtime Architecture

## Purpose

LOT-06.6 inserts an operational containment layer between provider health and economic writes.

~~~text
ib_async events
-> IBKROperationalEventBridge
-> IBKROperationalGuard
-> IBKRExecutionAdapter
-> placeOrder / cancelOrder
~~~

## Dynamic LIMIT validation

~~~text
validExchanges + marketRuleIds
-> routing marketRuleId
-> reqMarketRule
-> lowEdge / increment schedule
-> active increment
-> price grid validation
-> provider write
~~~

Market-rule data stays inside the IBKR adapter boundary.

## Pacing ownership

ib_async owns the transport request queue.

PyTradeKit validates the configured MaxRequests and RequestsInterval and observes throttleStart / throttleEnd.

No second request queue is introduced.

## Connectivity ownership

PyTradeKit keeps separate state for socket connectivity, provider connectivity, reconciliation and market-data readiness.

## Recovery invariant

~~~text
reconnect
-> fresh provider state
-> generic reconciliation
-> CONSISTENT/HIGH
-> write readmission
~~~

Connectivity restoration alone never replays or re-admits economic writes.

## Market data

1101 sets market_data_resubscription_required.

Market-data admission remains closed until explicit resubscription evidence exists.

## Economic replay

The operational runtime has no placeOrder or cancelOrder call site.

Provider recovery and economic intent remain separate concerns.
