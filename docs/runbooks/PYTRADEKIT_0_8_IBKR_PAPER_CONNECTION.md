# PyTradeKit 0.8 IBKR PAPER Connection Runbook

## Purpose

This runbook validates the LOT-06.1 connection path against a local IB Gateway PAPER session.

It does not place orders.

## Prerequisites

Install the IBKR extra:

~~~bash
python -m pip install -e ".[ibkr]"
~~~

Required transport pin:

~~~text
ib_async==2.1.0
~~~

Start IB Gateway and log in to the PAPER account.

Configure the API socket for PAPER:

~~~text
host 127.0.0.1
port 4002
~~~

The runtime does not support LIVE ports.

## Environment

Set the expected PAPER account:

~~~bash
export PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID="DUXXXXXXX"
~~~

Optional settings:

~~~bash
export PYTRADEKIT_IBKR_HOST="127.0.0.1"
export PYTRADEKIT_IBKR_PORT="4002"
export PYTRADEKIT_IBKR_CLIENT_ID="1"
export PYTRADEKIT_IBKR_CONNECT_TIMEOUT_SECONDS="10"
~~~

Do not use client ID 0 for the qualified LOT-06.1 runtime.

## Execute the safe probe

~~~bash
python scripts/probe_ibkr_paper_connection.py \
  --output artifacts/qualification/brokers/ibkr/real-paper-connection.json
~~~

Expected success:

~~~text
IBKR PAPER connection probe: PASS
economic order submitted: false
PAPER certification claimed: false
~~~

## Evidence captured

The artifact contains only sanitized fields:

~~~text
masked account
host
port
client id
transport name
transport version
socket connected
protocol ready
account verified
server version
startup readiness
~~~

No credential is stored.

The full account identifier is not stored.

## Failure guide

ConnectionRefusedError generally means IB Gateway is not running, API socket access is disabled, or the port does not match.

Account mismatch means the configured expected account is not visible in the connected API session.

Protocol not ready means the socket opened but the API synchronization did not reach the ready state.

## Qualification boundary

A successful probe means:

~~~text
real PAPER connection works
~~~

It does not mean:

~~~text
MARKET qualified
LIMIT qualified
CANCEL qualified
C3 PAPER qualified
TRADING_READY
~~~

Those require subsequent LOT-06 qualification stages.
