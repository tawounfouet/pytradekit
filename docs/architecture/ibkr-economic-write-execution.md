# IBKR Economic Write Execution Architecture

## Purpose

LOT-06.5 connects the canonical ExecutionPort to the qualified IBKR PAPER boundary.

~~~text
Order
-> execution binding
-> LOT-05.3 command mapping
-> LOT-06.4 reservation
-> SDK objects
-> placeOrder exactly once
-> callback/reconciliation
~~~

## Write admission

A provider-local IBKREconomicWriteAdmission must be open before submit or cancel.

It requires PAPER endpoint verification, account readiness, completed reconciliation, API write enablement and explicit economic write enablement.

## Submission identity

OrderId, orderRef, clientId + orderId and permId remain separate identity roles.

Only permId may become the canonical external_order_id.

## No retry

Once placeOrder or cancelOrder is attempted, any exception is an uncertain economic outcome.

~~~text
exception after provider call
-> UNCERTAIN
-> reconcile
-> no automatic retry
~~~

## LIMIT safety

Static-tick LIMIT orders can be represented.

Dynamic market-rule LIMIT orders remain fail-closed until reqMarketRule semantics are qualified.

## Query path

query_order reuses LOT-06.4 callback correlation and LOT-05.4 status normalization.

No cumulative orderStatus callback can create a synthetic Fill.

## Runtime readiness

The implementation exists, but production trading readiness remains closed until real PAPER certification evidence exists.
