# PyTradeKit v0.5.0 - Production Qualification and Release Runbook

**Target:** `v0.5.0`  
**Provider scope:** Alpaca PAPER only  
**LIVE:** out of scope

## 1. Release policy

`v0.5.0` may be released only when every required production qualification gate is `PASS`.

A green CI build is necessary but not sufficient.

Required gate families:

```text
CI quality
PostgreSQL restart E2E
crash-window fault injection
graceful SIGTERM shutdown
429/5xx semantics
real PAPER runtime start/restart
real PAPER MARKET/LIMIT/CANCEL
real trade_updates
real uncertain submit recovery
real cleanup to baseline
operator runbook review
```

## 2. Dedicated PAPER account

Use a PAPER account dedicated to PyTradeKit qualification.

Before running the harness:

```text
no unknown open orders
no unexpected positions
account not blocked
trading not blocked
```

Manual activity on the same account can intentionally block readiness.

## 3. Required environment

```bash
export PYTRADEKIT_RUNTIME_ENVIRONMENT="PAPER"
export PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID="..."

export PYTRADEKIT_ALPACA_PAPER_API_KEY="..."
export PYTRADEKIT_ALPACA_PAPER_SECRET_KEY="..."

export PYTRADEKIT_DATABASE_URL="postgresql+psycopg://..."

export PYTRADEKIT_QUALIFICATION_ACCOUNT_ID="<canonical UUID>"
export PYTRADEKIT_QUALIFICATION_INSTRUMENT_ID="<canonical UUID>"

export PYTRADEKIT_ALPACA_ORDER_PROBE_SYMBOL="AAPL"
export PYTRADEKIT_ALPACA_DATA_FEED="iex"
```

Never paste credentials into issue descriptions, PR comments, logs, or qualification artifacts.

## 4. Order-writing acknowledgement

Controlled PAPER order qualification additionally requires:

```bash
export PYTRADEKIT_ALPACA_ORDER_PROBE_ACK="I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED"
```

Without this exact value, the order probe must fail closed.

## 5. CI qualification

The branch must pass:

```text
Typography
Ruff
mypy strict
Import architecture contracts
Architecture/public contracts
Unit tests
Property tests
PostgreSQL integration tests
Production fault qualification
Release artifact qualification
```

Record the exact Git commit SHA and Actions run ID.

## 6. Crash-window qualification

The PostgreSQL qualification matrix covers:

```text
BEFORE_INBOX_CLAIM
AFTER_INBOX_CLAIM
AFTER_FILL_PERSIST
AFTER_CANONICAL_APPLY
AFTER_OUTBOX_ADD
BEFORE_COMMIT
AFTER_COMMIT
```

Expected:

```text
every pre-commit injected crash -> zero durable new economic effect
after-commit injected crash -> exactly one durable economic effect
replay -> no duplicate effect
```

## 7. Real PAPER harness

Run while the US equity market is open if controlled MARKET orders are enabled:

```bash
python scripts/alpaca_paper_v050_qualification.py   --with-orders   --ci-qualified   --runbook-reviewed   --output artifacts/qualification/v050-paper.json
```

The harness has no LIVE mode.

## 8. What the real harness does

With `--with-orders`:

```text
controlled MARKET buy
simulated post-ack response loss
recovery by client_order_id
controlled LIMIT buy safely below bid
single cancel attempt
cleanup MARKET sell
baseline position comparison
trade_updates observation
```

Then it executes two full runtime cycles against the same PostgreSQL state:

```text
start
TRADING_READY
graceful stop
rebuild runtime composition
start again
TRADING_READY
graceful stop
```

## 9. Real PAPER pass criteria

Required:

```text
order probe result = PASS
trade_updates event_count > 0
uncertain recovery used exactly one submit attempt
resubmitted = false
final position = baseline position
runtime cycle 1 trading_ready = true
runtime cycle 2 trading_ready = true
both shutdowns drained = true
```

## 10. Release gate check

Run:

```bash
python scripts/check_v050_release_gate.py   artifacts/qualification/v050-paper.json
```

Expected:

```text
PyTradeKit v0.5.0 production qualification gate: PASS
```

Any `PENDING` or `FAIL` blocks the release.

## 11. If the market is closed

Do not weaken the order probe.

Options:

```text
run read-only checks now
schedule order-writing qualification for the next open session
keep real order gates PENDING
do not release v0.5.0 yet
```

## 12. If cleanup fails

Stop.

Inspect the PAPER account.

Do not immediately rerun the probe while:

```text
final position != baseline
open qualification order exists
cancel outcome is uncertain
```

Restore a known account state manually before retrying.

## 13. If the runtime restart is NOT_READY

Inspect the report gaps.

Typical causes:

```text
cash changed between cycles
unexpected open order
unexpected position
unprocessed Inbox
provider order divergence
stream not ready
database unavailable
```

Do not mark the gate PASS manually.

## 14. Evidence retention

Retain:

```text
commit SHA
CI run URL/ID
sanitized v050-paper.json
market date/time
symbol
SDK target
PostgreSQL version
Python version
operator name or release approver
```

Never retain secrets in qualification artifacts.

## 15. Version bump policy

Until all required gates pass:

```text
pyproject version remains pre-release repository state
v0.5.0 tag must not be created
```

Only after the release gate passes:

```text
update package version
finalize docs/releases/0.5.0.md
merge qualification branch
tag v0.5.0
publish release artifact
```

## 16. Rollback policy

If a regression is found after release:

```text
stop new admissions
preserve database
stop provider stream
reconcile provider state
revert deployment
do not roll back economic provider facts
```

Database rollback must never erase economic evidence already required for reconciliation.

## 17. Final release principle

> Release evidence must come from the environment it claims to qualify. CI proves deterministic safety properties; Alpaca PAPER proves the provider integration.
