# IBKR Provider Identity Model

## Purpose

The IBKR anti-corruption layer preserves provider identity semantics without promoting them into canonical PyTradeKit identifiers.

~~~text
canonical
OrderId / FillId / InstrumentId

provider
clientId / orderId / permId / orderRef / execId / conId
~~~

These identity systems are deliberately different.

## Order identity layers

~~~text
clientId + orderId
        |
        v
session routing identity

orderRef
        |
        v
client correlation

permId
        |
        v
stable provider order identity
~~~

ProviderOrderIdentity is emitted only after a non-zero permId exists.

The adapter must never use orderId as a fallback external order identity.

## Session rebinding

The same permId may later be observed through a different session routing key.

The provider-local identity registry therefore permits:

~~~text
(clientId=1, orderId=10, permId=700, orderRef=ptk-a)

later

(clientId=2, orderId=91, permId=700, orderRef=ptk-a)
~~~

but rejects conflicting economic correlation.

## Execution identity

~~~text
execId
->
ProviderFillIdentity.external_fill_id
~~~

An execution identity is an observation identity.

It is not sufficient by itself to create a new economic Fill.

## Execution corrections

IBKR can publish a corrected execution with an execId whose final revision differs from the previous observation.

The ACL therefore represents the relationship explicitly with IBKRExecutionCorrection.

The identity layer only checks that two IDs can belong to the same correction family.

A later execution mapper must verify the remaining provider fields before classifying the new observation as an economic correction.

## Contract identity

~~~text
conId
->
ProviderInstrumentIdentity.external_id
~~~

The full Contract to Instrument mapping is intentionally deferred to LOT-05.2.

## Isolation

The identity model imports neither ibapi nor ib_async.

Its types must remain inside pytradekit.brokers.adapters.ibkr.

The generic provider models remain unaware of IBKR field names.
