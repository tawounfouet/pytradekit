# Orders Guide

## Creating an order

Application callers use SubmitOrderCommand rather than mutating an Order aggregate directly.

~~~python
from decimal import Decimal

from pytradekit.orders import OrderSide, OrderType, TimeInForce
from pytradekit.orders.application import SubmitOrderCommand
from pytradekit.shared import CorrelationId, InstrumentId, Quantity

command = SubmitOrderCommand(
    instrument_id=InstrumentId.new(),
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=Quantity(Decimal("10")),
    time_in_force=TimeInForce.DAY,
    correlation_id=CorrelationId.new(),
)
~~~

MARKET orders must not define limit_price.

LIMIT orders must define limit_price.

## Application services

The 0.2 application surface is:

- SubmitOrder
- CancelOrder
- HandleExecutionReport
- ProcessFill
- GetOrder

SubmitOrder creates the aggregate, validates it, persists it, issues one execution submission, and applies the immediate known result.

CancelOrder records CANCEL_REQUESTED before crossing the execution boundary.

HandleExecutionReport applies provider-neutral external facts.

ProcessFill protects the economic quantity from duplicate application.

GetOrder returns OrderSnapshot rather than exposing a mutable repository object.

## Submission uncertainty

SubmissionStatus.UNCERTAIN means that the transport outcome is unknown.

Do not infer rejection.

Do not issue an automatic replacement order.

Instead, query or reconcile through ExecutionPort.query_order and feed the resulting ExecutionReport into HandleExecutionReport.

## Cancellation uncertainty

CancelStatus.UNCERTAIN leaves the order in CANCEL_REQUESTED with ExecutionCertainty.UNCERTAIN.

A second CancelOrder call is intentionally rejected while that request remains unresolved.

## Fill identity

Fill.deduplication_key prefers the provider external_fill_id.

When no provider identity is available it falls back to the internal FillId.

A stable provider fill identifier should therefore be preserved by real broker adapters in future milestones.

## Reading state

~~~python
snapshot = get_order.execute(order_id)

if snapshot is not None:
    print(snapshot.status)
    print(snapshot.filled_quantity)
    print(snapshot.remaining_quantity)
~~~

OrderSnapshot is the application read DTO for 0.2.

## State ownership

The Order aggregate owns lifecycle invariants.

Application services own orchestration.

Broker adapters own provider translation.

No layer should bypass these responsibilities by mutating status fields directly.
