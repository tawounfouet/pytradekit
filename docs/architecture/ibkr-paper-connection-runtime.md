# IBKR PAPER Connection Runtime

## Purpose

PyTradeKit 0.8.0b2 LOT-06.1 selects the first concrete IBKR transport while preserving the broker-neutral core.

The selected implementation is:

~~~text
ib_async==2.1.0
~~~

It is optional and provider-local.

## Boundary

~~~text
Domain / OMS / Portfolio / Risk / Reconciliation / Safety
                         |
                         v
               broker-neutral ports
                         |
                         v
               IBKR anti-corruption layer
                         |
                         v
               IBKR PAPER runtime
                         |
                         v
                 ib_async 2.1.0
                         |
                         v
               IB Gateway PAPER 4002 or explicit TWS PAPER 7497
~~~

No canonical layer imports ib_async.

## Connection readiness

A TCP connection alone is not sufficient.

LOT-06.1 requires:

~~~text
socket connected
+
ib_async client ready
+
expected managed account visible
+
PAPER endpoint validated
~~~

ib_async documents that its client connection becomes ready only after the API synchronization phase, including nextValidId readiness.

## Client ID

The qualified runtime does not use clientId 0.

clientId 0 can auto-bind manual orders in the high-level ib_async order-management path.

PyTradeKit LOT-04 explicitly excludes automatic adoption of manual TWS orders.

Therefore:

~~~text
clientId > 0
~~~

is required by LOT-06.1.

## Startup versus trading readiness

The runtime returns StartupReadinessReport.

~~~text
READY_FOR_STARTUP
!=
TRADING_READY
~~~

Trading readiness still requires read-side reconciliation and later economic-write qualification.

## Dependency policy

~~~text
official ibapi
-> still not bundled

ib_async
-> optional extra
-> exact version pin
-> provider adapter only
~~~

## Failure behavior

Transport connectivity failures map to ProviderUnavailableError.

Handshake or account identity inconsistencies map to ProviderProtocolError.

Raw provider exception messages are not exposed.

## Real PAPER probe

A safe manual probe exists:

~~~bash
PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID=DUXXXXXXX \
python scripts/probe_ibkr_paper_connection.py \
  --output artifacts/qualification/brokers/ibkr/real-paper-connection.json
~~~

The probe performs no economic write.

Its output is connection evidence, not certification.
