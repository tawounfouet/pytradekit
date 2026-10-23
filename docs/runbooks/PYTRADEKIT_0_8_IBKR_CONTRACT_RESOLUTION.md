# PyTradeKit 0.8 IBKR Contract Resolution Runbook

## Purpose

This runbook covers LOT-06.3 provider reference resolution.

No economic write is performed.

## Prerequisites

A LOT-06.1 PAPER connection must be available:

~~~text
IB Gateway
PAPER
port 4002
non-zero clientId
expected account verified
protocol ready
~~~

A canonical instrument binding must also already exist:

~~~text
conId
symbol
InstrumentId
~~~

## Deterministic qualification

Run:

~~~bash
python scripts/qualify_ibkr_0_8_contract_resolution.py \
  --output artifacts/qualification/brokers/ibkr/contract-reference-resolution.json
~~~

This uses no provider network call.

## Real PAPER probe

Provide the normal LOT-06.1 environment variables, including:

~~~text
PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID
PYTRADEKIT_IBKR_HOST
PYTRADEKIT_IBKR_PORT
PYTRADEKIT_IBKR_CLIENT_ID
PYTRADEKIT_IBKR_CONNECT_TIMEOUT_SECONDS
~~~

Then run:

~~~bash
python scripts/probe_ibkr_paper_contract_resolution.py \
  --contract-id 265598 \
  --symbol AAPL \
  --instrument-id <canonical-uuid> \
  --output artifacts/manual/ibkr-paper-contract-resolution.json
~~~

## Expected result

A safe result records:

~~~text
provider = ibkr
environment = PAPER
conId exact match
symbol exact match
routing exchange = SMART
primary exchange retained
market rule IDs retained
economic_write_used = false
paper_certification_claimed = false
live_available = false
~~~

## Failure interpretation

No provider result:

~~~text
resolution = unresolved
~~~

Multiple or contradictory provider results:

~~~text
ProviderProtocolError
~~~

Missing SDK request capability:

~~~text
ProviderUnavailableError
~~~

Malformed ContractDetails payload:

~~~text
ProviderProtocolError
~~~

## Safety

Do not use LOT-06.3 evidence as proof that MARKET, LIMIT or CANCEL is certified on IBKR PAPER.

The lot qualifies reference resolution only.
