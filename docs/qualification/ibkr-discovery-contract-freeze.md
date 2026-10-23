# PyTradeKit 0.8 IBKR Discovery Contract Freeze Qualification

## Qualification class

LOT-04 is an architecture and contract qualification.

It is not a provider PAPER certification.

No IBKR CertifiedCapability is emitted.

## Required results

~~~text
IBKR freeze builds deterministically
PAPER environment fixed
IB Gateway target fixed
PAPER port 4002 accepted
LIVE port 4001 rejected
TWS PAPER port 7497 accepted when explicitly validating TWS
TWS LIVE port 7496 rejected
permId frozen as stable external order identity
orderId frozen as adapter-local session identity
execId frozen as execution identity
conId frozen as instrument identity
reconnect implicit resubmission forbidden
target capabilities explicit
deferred capabilities explicit
unresolved PAPER questions explicit
no ibapi dependency
no ib_async dependency
no provider-specific core branch
no LIVE runtime capability
~~~

## Certification statement

Passing LOT-04 proves:

~~~text
IBKR discovery is compatible with the current broker-neutral contract candidate.
~~~

It does not prove:

~~~text
IBKR adapter implemented
IBKR integration qualified
IBKR PAPER qualified
IBKR LIVE qualified
~~~
