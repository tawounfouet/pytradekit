# PyTradeKit 0.8 IBKR Read-Side Reconciliation Runbook

## Purpose

This runbook describes the LOT-06.2 read-side gate.

No order is placed or cancelled by this stage.

## Required runtime state

Start from a qualified LOT-06.1 connection:

~~~text
IB Gateway PAPER
port 4002
non-zero clientId
protocol ready
expected account verified
~~~

## Required canonical evidence

Before a FULL snapshot can be considered complete, supply:

~~~text
explicit account restriction evidence
pre-qualified conId instrument mappings
order identity resolver
read-side coverage evidence
~~~

## Coverage warning

Do not mark order or execution history complete merely because ib_async returned a list.

The provider history may be bounded by the session or request window.

If coverage cannot be proven for the reconciliation cut:

~~~text
orders_complete = false
or
fills_complete = false
~~~

The resulting BrokerSnapshot must remain PARTIAL.

## Startup gate

Expected progression:

~~~text
READY_FOR_STARTUP
-> capture internal state
-> capture IBKR broker state
-> compare
-> resolve supported mismatches
-> fresh verification
-> CONSISTENT / HIGH
-> economic write gate still blocked
~~~

## Safe interpretation

A PASS on LOT-06.2 means:

~~~text
read-side normalization qualified
startup reconciliation semantics qualified
write admission still closed
~~~

It does not mean:

~~~text
MARKET qualified on IBKR PAPER
LIMIT qualified on IBKR PAPER
CANCEL qualified on IBKR PAPER
C3 certified
TRADING_READY
~~~
