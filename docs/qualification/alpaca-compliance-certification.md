# PyTradeKit 0.8 - Alpaca Compliance Certification

## Purpose

LOT-03 proves the broker compliance model against the existing Alpaca PAPER provider.

The qualification uses two evidence classes:

- retained deterministic integration evidence;
- retained real Alpaca PAPER evidence.

No fake PAPER evidence is promoted to C3.

## Retained real PAPER source

The real provider evidence was produced during the qualified PyTradeKit 0.5 release.

~~~text
source release        v0.5.0
qualified commit      a7768911b56bb25a7efd24aae12f3cb032a5c9ef
release commit        7e844a0c3bfa564638530c43fe59df31d9d9bd1b
deterministic CI run  39789341350
real PAPER run        39789766678
artifact ID           12430172671
artifact name         pytradekit-v050-paper-qualification
~~~

Artifact digests:

~~~text
artifact ZIP SHA-256
587c0238c5b4d36d9cbd63603dd48f8367c0cf0defc64a6a7936acd95a925b3f

v050-paper.json SHA-256
f4b271d0bf3148a8b400bdee6c10525d07b1ee5b033dc08f981a70c136ca1ab1
~~~

The normalized retained record is:

~~~text
docs/qualification/evidence/alpaca/v050-paper-20261022.json
~~~

It contains only sanitized capability proof and provenance.

## Source gate state

The retained qualification has:

~~~text
release_ready                         true

ci_quality_gate                       PASS
postgres_restart_e2e                  PASS
crash_window_faults                   PASS
graceful_shutdown                     PASS
provider_429_5xx_semantics            PASS

real_paper_runtime_start_restart      PASS
real_paper_market_limit_cancel        PASS
real_paper_trade_updates              PASS
real_paper_uncertain_recovery         PASS
real_paper_cleanup                    PASS

incident_runbook                      PASS
~~~

## Real PAPER observations reused by LOT-03

The retained provider proof contains:

~~~text
MARKET order filled
LIMIT order submitted
CANCEL observed
client_order_id recovery
resubmitted = false
submit attempts = 1
private trade_updates = 9
fill events with execution IDs
baseline PAPER position restored
two runtime start/restart cycles
TRADING_READY on both cycles
graceful shutdown on both cycles
IEX bid/ask quote observed
PAPER account query observed
cash and position observations
~~~

## Alpaca capability manifest

LOT-03 maps the frozen Alpaca adapter into ProviderCapabilityManifest.

Declared capabilities:

~~~text
ACCOUNT_QUERY
ORDER_QUERY
MARKET_ORDER
LIMIT_ORDER
CANCEL_ORDER
PARTIAL_FILL
POSITION_QUERY
BALANCE_QUERY
CLIENT_ORDER_REFERENCE
EXECUTION_FACTS
RECONNECT_RECOVERY
LATEST_QUOTE
~~~

Not declared:

~~~text
REPLACE_ORDER
~~~

Provider envelope:

~~~text
provider          alpaca
environment       PAPER
adapter version   0.5.0-frozen
SDK               alpaca-py 0.44.0
asset class       US equity
order types       MARKET, LIMIT
time in force     DAY
market data       IEX latest quote
~~~

## Certification matrix

| Capability | LOT-03 level | Evidence |
| --- | ---: | --- |
| ACCOUNT_QUERY | C3 | Real PAPER account/runtime evidence |
| ORDER_QUERY | C3 | Real client reference recovery query |
| MARKET_ORDER | C3 | Real PAPER MARKET fill |
| LIMIT_ORDER | C3 | Real PAPER LIMIT order |
| CANCEL_ORDER | C3 | Real PAPER cancel |
| PARTIAL_FILL | C2 | Deterministic provider state mapping only |
| POSITION_QUERY | C3 | Real PAPER position baseline and reconciliation |
| BALANCE_QUERY | C3 | Real PAPER account cash observation |
| CLIENT_ORDER_REFERENCE | C3 | Real recovery by client_order_id with one submit |
| EXECUTION_FACTS | C3 | Real private trade_updates with execution IDs |
| RECONNECT_RECOVERY | C3 | Two real runtime start/restart cycles |
| LATEST_QUOTE | C3 | Real IEX bid/ask preflight |
| REPLACE_ORDER | Not declared | Out of frozen Alpaca scope |

## Why PARTIAL_FILL remains C2

The adapter has deterministic mapping for:

~~~text
Alpaca PARTIALLY_FILLED
-> PyTradeKit PARTIALLY_FILLED
~~~

and:

~~~text
Alpaca partial_fill trade event
-> PyTradeKit PARTIALLY_FILLED
~~~

However, the retained real PAPER artifact contains full fill events and no real partial_fill event.

Therefore LOT-03 does not claim C3 for PARTIAL_FILL.

## Common harness proof

Alpaca certification is generated through the same ComplianceHarness introduced in LOT-02.

The provider-specific code supplies:

~~~text
ProviderCapabilityManifest
Alpaca retained evidence
provider-specific scenario executor
~~~

The common compliance layer still owns:

~~~text
ComplianceRequirement
ComplianceScenario
ComplianceResult
ComplianceEvidence
ComplianceReport
CertifiedCapability
CertificationRegistry
StaleEvidencePolicy
~~~

## Evidence freshness

The certification is linked to:

~~~text
provider
PAPER environment
adapter version
alpaca-py version
BrokerAdapterContract version
qualified source commit
retained source artifact
~~~

Changing the adapter version invalidates the retained certification through StaleEvidencePolicy.

## Rerun path

The historical evidence can be reused while it remains valid for the frozen adapter.

A fresh real provider qualification can also be generated with:

~~~text
.github/workflows/v080-alpaca-paper-certification.yml
~~~

The workflow:

~~~text
runs the controlled real Alpaca PAPER probe
normalizes its sanitized evidence
runs the 0.8 common ComplianceHarness
generates a ComplianceRun
uploads the normalized evidence and certification report
~~~

The workflow has no LIVE mode.

## Result

LOT-03 establishes the first concrete provider certification under the 0.8 compliance model.

The important result is not:

~~~text
Alpaca certified
~~~

It is:

~~~text
Alpaca ACCOUNT_QUERY           C3
Alpaca ORDER_QUERY             C3
Alpaca MARKET_ORDER            C3
Alpaca LIMIT_ORDER             C3
Alpaca CANCEL_ORDER            C3
Alpaca PARTIAL_FILL            C2
Alpaca POSITION_QUERY          C3
Alpaca BALANCE_QUERY           C3
Alpaca CLIENT_ORDER_REFERENCE  C3
Alpaca EXECUTION_FACTS         C3
Alpaca RECONNECT_RECOVERY      C3
Alpaca LATEST_QUOTE            C3
~~~

Certification remains capability-specific.
