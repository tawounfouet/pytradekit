# IBKR Discovery Guide

## Scope

This guide explains the frozen PyTradeKit 0.8.0a4 IBKR discovery contract.

No provider network connection is performed by LOT-04.

No IBKR SDK dependency is installed.

No PAPER order is created.

## Inspect the freeze

~~~python
from pytradekit.brokers.adapters.ibkr import build_ibkr_contract_freeze

freeze = build_ibkr_contract_freeze()

print(freeze.to_dict())
~~~

Expected provider envelope:

~~~text
provider        ibkr
environment     PAPER
runtime         IB_GATEWAY
transport       TWS API socket
paper port      4002
asset class     equity
order types     MARKET, LIMIT
time in force   DAY
~~~

## Validate PAPER port

~~~python
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientSurface,
    validate_ibkr_paper_port,
)

validate_ibkr_paper_port(
    surface=IBKRClientSurface.IB_GATEWAY,
    port=4002,
)
~~~

The following must fail:

~~~text
4001
7496
unexpected custom ports
~~~

## Identity policy

Use:

~~~text
orderRef -> client reference candidate
permId   -> external order id
execId   -> external fill id
conId    -> external instrument id
~~~

Keep:

~~~text
orderId
clientId
nextValidId
~~~

inside the IBKR adapter runtime.

## Do not infer certification

The freeze only states:

~~~text
candidate mapping
target capability
known provider behavior
open PAPER question
implementation boundary
~~~

It does not create:

~~~text
CertifiedCapability
C2
C3
PAPER evidence
~~~

Those require the later implementation and qualification LOTs.

## Source precedence

When implementing the adapter, use this precedence:

~~~text
1. current official IBKR documentation
2. retained real PAPER evidence
3. frozen PyTradeKit canonical invariants
4. adapter implementation detail
~~~

When documentation and observed PAPER behavior disagree, preserve the observation as evidence and update the provider adapter. Do not silently change the canonical core.
