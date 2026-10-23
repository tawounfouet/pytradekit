# IBKR Discovery and Contract Freeze

## Purpose

PyTradeKit 0.8.0a4 freezes the first IBKR implementation envelope before any SDK-backed adapter is introduced.

The target is:

~~~text
IB Gateway
TWS API socket
PAPER
US equities
MARKET
LIMIT
CANCEL
DAY
~~~

The governing rule remains:

> Normalize semantics, not provider features.

## Frozen identities

~~~text
canonical client reference -> orderRef candidate
canonical external order id -> permId
adapter session order id    -> orderId
canonical external fill id  -> execId
provider instrument id      -> conId
runtime connection id       -> clientId
~~~

orderId is never promoted to the canonical order identity.

## Submission boundary

placeOrder is a transport action.

The stable provider acknowledgement is not assumed until provider callbacks produce enough identity and state to attach a non-zero permId.

~~~text
placeOrder
-> openOrder / orderStatus / error
-> stable permId observed?
   yes -> canonical acknowledgement may be emitted
   no  -> uncertain outcome and reconciliation
~~~

## Readiness

The first IBKR runtime requires:

~~~text
socket connected
protocol negotiated
nextValidId received
account verified
PAPER endpoint verified
reconciliation complete
~~~

nextValidId is adapter sequencing state.

It never becomes a PyTradeKit OrderId.

## Reconnect

The IBKR setting:

~~~text
maintainAndResubmitOrdersOnReconnect
~~~

must be disabled for qualification.

PyTradeKit owns recovery semantics:

~~~text
disconnect
-> uncertain when economic outcome is unknown
-> reconnect
-> reconcile
-> admit new economic writes only after truth is restored
~~~

## Contract compatibility

No IBKR-specific change is required in:

~~~text
Domain
OMS
Risk
Portfolio
Reconciliation
Safety
ExecutionPort
BrokerSnapshotPort
ProviderOrderIdentity
ProviderFillIdentity
ProviderInstrumentIdentity
~~~

Provider-neutral models are reused through mappings.

The current Alpaca-only RuntimeProfile is not generalized with provider branches. The IBKR runtime will use provider-local composition until a common runtime abstraction is proven by both providers.

## PAPER endpoint hard-lock

~~~text
TWS PAPER        7497
IB Gateway PAPER 4002

TWS LIVE         7496
IB Gateway LIVE  4001
~~~

The frozen automated runtime uses IB Gateway PAPER on port 4002.

LIVE ports are explicit rejection values.

## SDK policy

The official TWS API 10.49+ is documented by IBKR as GPL.

PyTradeKit remains Apache-2.0.

The official SDK is therefore not bundled by LOT-04.

ib_async remains a candidate implementation only. The canonical contract does not depend on it.

## PAPER questions

The following facts remain intentionally unresolved until a real provider probe:

~~~text
orderRef behavior in target PAPER account
callback ordering
non-zero permId timing
partial fill behavior
execId correction behavior
execution replay on reconnect
cash/account tag mapping
market data entitlement behavior
effective pacing
~~~

Unresolved facts are blockers to certification, not invitations to guess.


## Verified source baseline

The freeze was checked against the current IBKR TWS API documentation on 2026-10-23.

Primary sources include the current TWS API changelog, connection handshake documentation, sync wrapper connection documentation, Order and Execution references, contract identity guidance, order placement callbacks, API settings and PAPER limitations.

The implementation must re-check those official sources before changing the pinned provider transport or SDK version.
