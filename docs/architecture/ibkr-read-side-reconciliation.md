# IBKR Read-Side Snapshot & Startup Reconciliation

## Purpose

LOT-06.2 turns synchronized IBKR PAPER state into generic reconciliation evidence.

~~~text
IB Gateway PAPER
-> ib_async synchronized state
-> IBAsyncPaperTransport read facade
-> IBKRBrokerSnapshotPort
-> BrokerSnapshot
-> generic ReconcileAccount
-> ConsistencyStatus / StateConfidence
~~~

## Read-side only

The adapter consumes:

~~~text
accountValues()
portfolio()
trades()
fills()
~~~

It does not call:

~~~text
placeOrder()
cancelOrder()
~~~

## Snapshot completeness

Provider inventory completeness is never inferred.

IBKRReadSideCoverageEvidence must explicitly state whether each inventory is complete for the reconciliation cut.

~~~text
unknown coverage
-> PARTIAL
-> no HIGH confidence convergence
~~~

## Order identity

~~~text
orderId
= session routing identity

permId
= durable external order identity

orderRef
= optional client correlation
~~~

A missing canonical OrderId does not erase the provider observation.

## Fill identity

~~~text
execId
= external fill identity
~~~

Unknown external fills remain explicit external activity.

## Instrument identity

~~~text
conId
= provider instrument identity
~~~

The adapter requires a pre-qualified IBKRInstrumentMappingResult. It never resolves a position by symbol alone.

## Admission

Read-side reconciliation may prove:

~~~text
CONSISTENT / HIGH
~~~

but LOT-06.2 still appends an economic-write admission failure.

~~~text
read-side reconciled
!=
TRADING_READY
~~~

The write path must be qualified separately.
