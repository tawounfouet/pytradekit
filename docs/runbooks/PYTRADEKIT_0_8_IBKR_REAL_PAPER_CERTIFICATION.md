# PyTradeKit 0.8 IBKR Real PAPER Certification Runbook

## Preconditions

Use a dedicated self-hosted Linux GitHub Actions runner with label:

~~~text
pytradekit-ibkr-paper
~~~

IB Gateway must already be authenticated to the PAPER account and listening on:

~~~text
127.0.0.1:4002
~~~

Configure repository secret:

~~~text
PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID
~~~

## Before running

Confirm the deterministic CI run for the exact target commit is green.

Choose a US equity symbol and matching conId.

Choose a valid passive LIMIT price. The LIMIT must remain open long enough to exercise CANCEL.

Run during a session where the controlled MARKET order can fill.

## Workflow inputs

~~~text
deterministic_ci_run_id
symbol
contract_id
limit_price
quantity
client_id
~~~

Use a dedicated non-zero client ID that is not used by another API session.

## Workflow

Trigger:

~~~text
IBKR Real PAPER Qualification
~~~

The workflow verifies the CI run belongs to the same commit before any provider order is permitted.

## Expected order sequence

~~~text
MARKET BUY
-> fill
-> dynamic LIMIT BUY
-> cancel
-> MARKET SELL cleanup
~~~

After cleanup the symbol position must equal the original baseline.

## Failure handling

If MARKET is uncertain, do not rerun immediately.

Inspect the PAPER account, orderRef activity, Trade state and executions first.

If LIMIT fills instead of remaining passive, restore the baseline and choose a safer passive limit before another qualification attempt.

If cleanup does not restore baseline, the workflow must remain failed.

## Evidence outputs

The uploaded artifact contains:

~~~text
real-paper-probe.json
retained-evidence.json
compliance-certification.json
~~~

All outputs are sanitized.

## Retention

After a successful workflow, review the artifact and retain the normalized evidence record under the project qualification evidence policy.

Do not hand-edit provider proof fields.

## PARTIAL_FILL

Do not promote PARTIAL_FILL from a full fill.

Keep it at C2 until a true partial fill is captured.

## LIVE

LIVE remains unavailable.
