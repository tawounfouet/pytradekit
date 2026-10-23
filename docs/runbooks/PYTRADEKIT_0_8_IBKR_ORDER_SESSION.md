# PyTradeKit 0.8 IBKR Order Session Runbook

## Purpose

This runbook covers LOT-06.4 order ID sequencing and callback correlation.

No economic write is performed.

## Deterministic qualification

Run:

~~~bash
python scripts/qualify_ibkr_0_8_order_session.py \
  --output artifacts/qualification/brokers/ibkr/order-session.json
~~~

The qualification validates:

~~~text
synchronized order ID reservation
clientId + orderId routing
orderRef correlation
permId late binding
unknown callback non-adoption
order error discrimination
no placeOrder
no cancelOrder
~~~

## Real PAPER sequence probe

Configure the existing LOT-06.1 variables:

~~~text
PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID
PYTRADEKIT_IBKR_HOST
PYTRADEKIT_IBKR_PORT
PYTRADEKIT_IBKR_CLIENT_ID
PYTRADEKIT_IBKR_CONNECT_TIMEOUT_SECONDS
~~~

Then run:

~~~bash
python scripts/probe_ibkr_paper_order_sequence.py \
  --order-reference ptk-manual-probe-001 \
  --currency USD \
  --output artifacts/manual/ibkr-paper-order-sequence.json
~~~

## What the probe proves

The probe proves only:

~~~text
IB Gateway PAPER connection is ready
nextValidId-derived sequence is available
getReqId can reserve an ID
clientId is explicit
orderRef can be correlated before submission
~~~

## What the probe does not prove

~~~text
placeOrder capability
cancelOrder capability
order acceptance
fill generation
PAPER C3 certification
TRADING_READY
LIVE
~~~

## Callback incidents

Unknown orderId:

~~~text
do not adopt
leave to read-side reconciliation
~~~

Other clientId:

~~~text
do not adopt as internal order
~~~

Conflicting orderRef:

~~~text
ProviderProtocolError
~~~

Conflicting permId:

~~~text
ProviderProtocolError
~~~

Negative error reqId:

~~~text
not an internal order error
~~~

## Safety

Never infer that an allocated orderId means an order was submitted.

Reservation and economic write are separate facts.
