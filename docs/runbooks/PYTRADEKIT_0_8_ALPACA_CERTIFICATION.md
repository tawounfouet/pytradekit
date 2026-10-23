# PyTradeKit 0.8 Alpaca PAPER Certification Runbook

## Scope

This runbook covers LOT-03 Alpaca compliance certification.

The provider environment is PAPER only.

There is no LIVE mode.

## Deterministic qualification

The default CI replays the retained normalized evidence record:

~~~text
docs/qualification/evidence/alpaca/v050-paper-20261022.json
~~~

Command:

~~~bash
python scripts/qualify_alpaca_0_8.py \
  --evidence-record docs/qualification/evidence/alpaca/v050-paper-20261022.json \
  --output artifacts/qualification/brokers/alpaca/compliance-run.json
~~~

Expected result:

~~~text
PyTradeKit 0.8 Alpaca compliance certification: PASS
~~~

## Fresh real PAPER qualification

Use the manual GitHub Actions workflow:

~~~text
v0.8.0a3 Alpaca PAPER Certification
~~~

Workflow file:

~~~text
.github/workflows/v080-alpaca-paper-certification.yml
~~~

Required repository secrets:

~~~text
PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID
PYTRADEKIT_ALPACA_PAPER_API_KEY
PYTRADEKIT_ALPACA_PAPER_SECRET_KEY
~~~

The workflow also requires:

~~~text
PAPER environment
dedicated account
market open for controlled MARKET qualification
explicit PAPER order acknowledgement
PostgreSQL
~~~

## Generated artifacts

The workflow uploads:

~~~text
source-paper.json
normalized-evidence.json
compliance-run.json
~~~

All generated qualification evidence must remain secret-safe.

## Failure handling

A failure must not be converted into C3.

Examples:

~~~text
market closed
provider unavailable
credential missing
cleanup failure
unexpected account identity
missing execution fact
unexpected resubmission
stale adapter version
~~~

The operator must inspect the dedicated PAPER account before retrying when order cleanup or remote outcome is uncertain.

## PARTIAL_FILL

PARTIAL_FILL remains C2 until real PAPER evidence includes a genuine provider partial_fill event.

Do not synthesize a partial fill solely to make the certification matrix green.

## Merge rule

LOT-03 is ready only when:

~~~text
Typography PASS
Ruff PASS
mypy strict PASS
Import Linter PASS
architecture PASS
LOT-01 PASS
LOT-02 PASS
LOT-03 deterministic certification PASS
full tests PASS
deployment qualification PASS
release artifact qualification PASS
~~~
