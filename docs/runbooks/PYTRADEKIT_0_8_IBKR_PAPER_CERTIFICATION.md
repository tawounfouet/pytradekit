# PyTradeKit 0.8 IBKR PAPER Certification Runbook

## 1. Deterministic certification

~~~bash
python scripts/qualify_ibkr_0_8_compliance.py \
  --commit-sha <candidate-sha> \
  --output artifacts/qualification/brokers/ibkr/compliance-certification.json
~~~

Expected result without real PAPER evidence:

~~~text
11 declared capabilities at C2
0 capabilities at C3
report complete = true
~~~

## 2. Real PAPER prerequisites

Use a dedicated IBKR Paper Trading Account and a running IB Gateway PAPER session.

Required runtime settings:

~~~text
PYTRADEKIT_IBKR_EXPECTED_ACCOUNT_ID
PYTRADEKIT_IBKR_HOST=127.0.0.1
PYTRADEKIT_IBKR_PORT=4002
PYTRADEKIT_IBKR_CLIENT_ID=<non-zero unique client>
~~~

Before controlled orders:

~~~text
PYTRADEKIT_IBKR_ORDER_PROBE_ACK=
I_UNDERSTAND_IBKR_PAPER_ORDERS_WILL_BE_CREATED
~~~

## 3. Local diagnostic probe

Choose an explicit safe LIMIT price for the selected US equity and configure:

~~~text
PYTRADEKIT_IBKR_ORDER_PROBE_SYMBOL=AAPL
PYTRADEKIT_IBKR_ORDER_PROBE_CONID=265598
PYTRADEKIT_IBKR_LIMIT_PRICE=<explicit-paper-limit-price>
PYTRADEKIT_IBKR_ORDER_PROBE_QUANTITY=1
PYTRADEKIT_IBKR_ORDER_PROBE_TIMEOUT_SECONDS=90
~~~

Then run:

~~~bash
python scripts/ibkr_paper_controlled_probe.py \
  --with-orders \
  --runbook-reviewed \
  --output artifacts/qualification/brokers/ibkr/real-paper-probe.json
~~~

This local run is diagnostic only. Do not pass `--ci-qualified` locally and do not treat the raw probe report as retained C3 evidence.

Do not rerun blindly after a failure involving an economic write. Inspect the PAPER account and retained orderRef values first.

## 4. Official C3 capture

Use the manual GitHub Actions workflow `IBKR Real PAPER Certification` only on a self-hosted macOS runner labelled `ibkr-paper` with IB Gateway already running on the same Mac.

The runner must expose the GitHub labels `self-hosted`, `macOS` and `ibkr-paper`. IB Gateway PAPER must be reachable from that same Mac at `127.0.0.1:4002`.

The workflow requires:

~~~text
a successful deterministic CI run ID for the exact candidate commit
explicit PAPER order acknowledgement
contract ID
symbol
safe LIMIT price
controlled quantity
dedicated non-zero client ID
~~~

The workflow verifies the CI run through the GitHub Actions API before any provider qualification step. The run must come from .github/workflows/ci.yml, succeed, and target the exact candidate commit.

It then executes:

~~~text
canonical IBKRExecutionAdapter probe
-> real-paper-probe.json
-> upload raw provider evidence
-> retained provider artifact_id
-> Actions-only normalize_ibkr_paper_evidence.py
-> SHA-256 verified real-paper-evidence.json
-> ComplianceHarness replay
-> real-paper-certification.json
~~~

The normalizer refuses to run outside the expected GitHub Actions workflow and validates GITHUB_SHA plus GITHUB_RUN_ID.

## 5. Certification replay

The workflow performs certification replay automatically:

~~~bash
python scripts/qualify_ibkr_0_8_compliance.py \
  --commit-sha "$GITHUB_SHA" \
  --paper-evidence artifacts/qualification/brokers/ibkr/real-paper-evidence.json \
  --output artifacts/qualification/brokers/ibkr/real-paper-certification.json
~~~

## 6. Failure handling

### MARKET uncertain

Do not rerun immediately.

Inspect synchronized trades, orderRef, permId and fills.

### LIMIT unexpectedly filled

Cleanup is derived from the fills actually observed for the probe, including any partial LIMIT execution. The baseline position must be restored before the artifact can be accepted.

### Failure after a provider fill

If the scenario stops after an observed provider fill but before normal cleanup, the probe attempts one best-effort cleanup before shutdown.

Do not replay cleanup if a cleanup order was already attempted. Inspect provider state first.

### Cancel not terminal

Do not claim CANCEL_ORDER C3.

### No partial fill

PARTIAL_FILL remains C2.

### Reconnect not reconciled

RECONNECT_RECOVERY remains C2.

## 7. Artifact retention

Retain the raw provider evidence artifact before C3 normalization, then retain:

~~~text
real-paper-evidence.json
real-paper-certification.json
~~~

The normalized bundle must contain the retained provider artifact ID, PAPER workflow run ID, deterministic CI run ID and canonical bundle SHA-256.

## 8. Release rule

Do not label IBKR TRADING_READY merely because some capabilities reached C3.

Readiness requires the exact release policy and required capability set to be satisfied.
