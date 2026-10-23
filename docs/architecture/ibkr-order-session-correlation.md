# IBKR Order Session Sequencing and Callback Correlation

## Purpose

LOT-06.4 establishes provider order routing before any economic write.

~~~text
protocol ready
-> synchronized request sequence
-> getReqId
-> clientId + orderId
-> orderRef
-> canonical OrderId
-> callback correlation
-> permId
~~~

## Sequencing

The runtime relies on the request sequence synchronized by ib_async during connect.

It does not maintain an independent counter.

Each reservation must advance monotonically within the PyTradeKit runtime.

## Identity separation

~~~text
OrderId
canonical business identity

orderRef
client correlation

clientId + orderId
session routing identity

permId
durable provider identity
~~~

These identifiers are never collapsed into one field.

## Callback admission

Only pre-reserved routes are treated as internal PyTradeKit order callbacks.

~~~text
reserved route
-> correlate

unknown route
-> do not adopt

other clientId
-> do not adopt
~~~

## openOrder

openOrder confirms orderRef and may introduce permId.

A conflicting orderRef or permId fails closed.

## orderStatus

The callback must preserve clientId, orderId and permId consistency across Trade.order and Trade.orderStatus.

Cumulative filled quantity is retained as state only.

No synthetic Fill is emitted.

## Errors

An error event is order-scoped only when its reqId/orderId matches a reserved internal order route.

Global and unrelated request errors are not reclassified as order rejections.

## Economic write status

LOT-06.4 performs no economic writes.

~~~text
placeOrder = not called
cancelOrder = not called
PAPER execution certification = not claimed
TRADING_READY = unavailable
LIVE = unavailable
~~~
