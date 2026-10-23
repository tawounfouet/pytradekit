# IBKR Contract Qualification & Reference Resolution Runtime

## Purpose

LOT-06.3 turns an IBKR conId into a qualified provider-to-canonical reference mapping.

~~~text
InstrumentId
+
conId
+
symbol
-> reqContractDetails
-> ContractDetails
-> LOT-05.2 normalization
-> IBKRInstrumentMappingResult
~~~

## Canonical identity first

The runtime does not create canonical instrument identities.

~~~text
(conId, symbol)
-> IBKRCanonicalInstrumentIdResolver
-> InstrumentId
~~~

If the canonical ID is missing, the provider request is skipped.

## Provider match rules

~~~text
0 matches
-> unresolved

1 exact conId + symbol match
-> qualified mapping

multiple exact matches
-> fail closed

non-exact provider response
-> fail closed
~~~

## Provider defaults

Zero-valued provider defaults for contract constraints are treated as unknown.

~~~text
0 minTick
-> None

0 minSize
-> None

0 sizeIncrement
-> None
~~~

No provider default becomes a fabricated trading constraint.

## Market rules

validExchanges and marketRuleIds are retained positionally.

If market rules exist:

~~~text
price_increment_mode = MARKET_RULE
canonical tick_size = None
~~~

minTick remains provider metadata only.

## Runtime boundary

~~~text
IBKRPaperConnectionRuntime
-> read_client()
-> reqContractDetails()
-> IBKRRuntimeContractDetailsClient
-> IBKRContractReferenceResolver
~~~

The SDK object exists only inside the IBKR adapter boundary.

## Economic write status

LOT-06.3 remains read-only.

~~~text
placeOrder = unavailable
cancelOrder = unavailable
TRADING_READY = unavailable
C3 IBKR PAPER certification = not claimed
LIVE = unavailable
~~~
