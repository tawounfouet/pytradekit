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

## 3. Manual controlled probe

Choose an explicit safe LIMIT price for the selected US equity.

~~~bash
python scripts/ibkr_paper_controlled_probe.py \
  --commit-sha <candidate-sha> \
  --contract-id 265598 \
  --symbol AAPL \
  --limit-price <explicit-paper-limit-price> \
  --with-orders \
  --ci-qualified \
  --output artifacts/qualification/brokers/ibkr/real-paper-evidence.json
~~~

Do not rerun blindly after a failure involving placeOrder.

Inspect the PAPER account and retained orderRef values first.

## 4. Certification replay

~~~bash
python scripts/qualify_ibkr_0_8_compliance.py \
  --commit-sha <candidate-sha> \
  --paper-evidence artifacts/qualification/brokers/ibkr/real-paper-evidence.json \
  --output artifacts/qualification/brokers/ibkr/real-paper-certification.json
~~~

## 5. GitHub workflow

Use the manual workflow `IBKR Real PAPER Certification` only on a self-hosted runner labelled `ibkr-paper` with IB Gateway already running.

The workflow requires the acknowledgement text as an explicit input.

## 6. Failure handling

### MARKET uncertain

Do not rerun immediately.

Inspect synchronized trades, orderRef, permId and fills.

### LIMIT unexpectedly filled

Cleanup must restore the baseline position before the artifact can be accepted.

### Cancel not terminal

Do not claim CANCEL_ORDER C3.

### No partial fill

PARTIAL_FILL remains C2.

### Reconnect not reconciled

RECONNECT_RECOVERY remains C2.

## 7. Artifact retention

Retain both:

~~~text
real-paper-evidence.json
real-paper-certification.json
~~~

Record the workflow run ID and artifact ID before freezing evidence into repository qualification records.

## 8. Release rule

Do not label IBKR TRADING_READY merely because some capabilities reached C3.

Readiness requires the exact release policy and required capability set to be satisfied.
