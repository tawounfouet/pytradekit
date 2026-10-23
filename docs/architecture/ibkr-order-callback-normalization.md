# IBKR Order Status & Callback Normalization

LOT-05.4 normalizes IBKR order callbacks into provider-neutral state without inventing economic facts.

## Callback model

~~~text
openOrder
orderStatus
error
execDetails
~~~

IBKR recommends monitoring these callback families together for robust order handling.

LOT-05.4 implements the first three. execDetails remains the source for individual execution identity in LOT-05.5.

## Status rules

~~~text
PendingSubmit -> transient
PreSubmitted  -> ACCEPTED
Submitted     -> ACCEPTED
PendingCancel -> transient
ApiCancelled  -> CANCELLED
Cancelled     -> CANCELLED
Filled        -> cumulative FILLED state only
Inactive      -> reconciliation
~~~

## Fill safety

A cumulative orderStatus can report filled quantity and average fill price, but it does not identify individual executions.

Therefore:

~~~text
cumulative fill state
!=
canonical Fill
~~~

PARTIALLY_FILLED and FILLED may appear in ProviderOrderStateSnapshot, but converting them to an ExecutionReport is blocked until execDetails supplies execution identity.

## Rejection safety

Inactive is not treated as rejection.

An explicit IBKR error 201 is normalized to REJECTED.

An explicit IBKR error 202 is normalized to CANCELLED.

Raw provider messages and advanced rejection payloads are not copied into canonical reason text.

## Ordering

The adapter does not assume openOrder arrives before orderStatus.

The identity registry can correlate callbacks from canonical context, then verify later openOrder identity evidence.

## SDK isolation

The callback layer uses only SDK-free observations:

~~~text
IBKROpenOrderObservation
IBKROrderStatusObservation
IBKROrderErrorObservation
~~~

No ibapi or ib_async type crosses the adapter boundary.
