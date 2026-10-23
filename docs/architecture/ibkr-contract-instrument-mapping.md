# IBKR Contract & Instrument Mapping

## Purpose

LOT-05.2 maps qualified IBKR stock contracts into existing PyTradeKit reference models.

The provider boundary consumes SDK-free records rather than ibapi or ib_async objects.

## Stable identity

Interactive Brokers recommends conId plus exchange as the preferred contract definition.

PyTradeKit therefore maps:

~~~text
conId
-> ProviderInstrumentIdentity.external_id

symbol
-> ProviderInstrumentIdentity.external_symbol
~~~

The canonical InstrumentId remains independent.

## Routing versus listing exchange

For the frozen stock scope:

~~~text
exchange = SMART
primaryExchange = native listing exchange
~~~

These concepts stay distinct.

## Contract specification

The safe mapping is:

~~~text
minSize
-> min_quantity

sizeIncrement
-> quantity_step
~~~

minTick requires special treatment.

When IBKR reports market rule IDs, minTick is retained only as provider metadata because it represents the smallest increment, not necessarily the complete price-dependent rule.

~~~text
marketRuleIds present
-> price increment mode MARKET_RULE
-> canonical tick_size None
~~~

Without market rules:

~~~text
minTick present
-> price increment mode STATIC
-> canonical tick_size minTick
~~~

Unknown provider constraints remain None.

## Provider metadata retained

The ACL retains:

~~~text
routing exchange
primary exchange
local symbol
trading class
valid exchanges
market rule IDs
reported min tick
suggested size increment
order types
time zone ID
stock type
~~~

No provider-only field is promoted into the canonical model without a matching semantic contract.

## SDK isolation

The mapper operates on:

~~~text
IBKRContractRecord
IBKRContractDetailsRecord
~~~

A future transport adapter may construct these records from either ib_async or direct TWS API types.

No SDK type crosses the adapter boundary.
