# IBKR Order Command Mapping

LOT-05.3 creates SDK-free IBKR placement commands from canonical PyTradeKit orders.

The mapping is intentionally separated from TWS session sequencing.

~~~text
Canonical Order
-> IBKR order command mapper
-> IBKRPlacementCommand
-> future transport
-> nextValidId / orderId allocation
-> placeOrder
~~~

The mapper supports only MARKET, LIMIT and DAY in the frozen scope.

client_order_id becomes the IBKR orderRef candidate.

The mapper never allocates orderId, never imports an IBKR SDK and never performs a provider call.

Known static quantity and price constraints are checked before transport. Dynamic market-rule pricing remains unresolved in the provider layer instead of being approximated by a static tick.

Transmission intent is explicit and defaults are not relied on:

~~~text
TRANSMIT
regular trading hours only
not what-if
no percentage-constraint override
~~~
