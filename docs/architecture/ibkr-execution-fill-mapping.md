# IBKR Execution Details & Fill Mapping

LOT-05.5 maps provider execution facts into canonical PyTradeKit Fill semantics.

## Core invariant

~~~text
one real IBKR execId
=
one canonical economic effect
~~~

Exact execId replay is idempotent.

A correction in the same execId family does not become a second Fill. It requires reconciliation because the current canonical Fill model does not support provider correction amendments.

## Mapping

~~~text
execId
-> ProviderFillIdentity.external_fill_id
-> Fill.external_fill_id

shares
-> Fill.quantity

price
-> Fill.price

permId
-> ExecutionReport.external_order_id

cumQty < expected order quantity
-> PARTIALLY_FILLED

cumQty == expected order quantity
-> FILLED
~~~

## Correlation

The mapper verifies:

~~~text
clientId
orderId
permId
orderRef
conId
symbol
side
quote currency
~~~

before emitting a Fill.

## Price revisions

If IBKR reports pendingPriceRevision, no canonical Fill is emitted.

The observation must be reconciled after stable provider evidence is available.

## Time normalization

A provider local timestamp is converted using its IANA timezone.

~~~text
provider wall clock
-> ZoneInfo
-> UTC
~~~

A local provider time is never relabeled as UTC.

## Commission

No commission is fabricated from execDetails.

Fill.fee remains None until a separate provider commission fact is semantically handled.

## SDK isolation

IBKRExecutionDetailsObservation is SDK-free.

No ibapi or ib_async type crosses the adapter boundary.
