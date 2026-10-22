# PyTradeKit 0.5 - Alpaca PAPER Incident Response Runbook

**Scope:** PyTradeKit `0.5.x`  
**Provider:** Alpaca PAPER only  
**Audience:** runtime operator / developer  
**Primary rule:** preserve economic truth before restoring availability.

## 1. Non-negotiable rules

During any incident:

```text
DO NOT blindly resubmit an uncertain order
DO NOT blindly repeat a cancel
DO NOT fabricate a Fill
DO NOT overwrite a divergent Position
DO NOT flatten an unexpected position automatically
DO NOT switch to LIVE
```

The recovery priority is:

```text
1. stop new submissions
2. keep observation and risk-reducing cancellation available when safe
3. preserve PostgreSQL state
4. observe Alpaca state
5. reconcile by stable identities
6. restore TRADING_READY only after gaps are closed
```

## 2. Runtime states

```text
STARTING
READY
DEGRADED
DRAINING
STOPPED
```

New submissions are allowed only in:

```text
READY
```

Cancellation remains allowed during:

```text
READY
DRAINING
```

Read-side reconciliation remains available until:

```text
STOPPED
```

## 3. First response to an incident

Capture the following sanitized evidence before changing state:

```text
TradingReadinessReport
RuntimeMetricsSnapshot
latest operational JSONL events
pending Inbox records
pending Outbox count
local reconcilable orders
Alpaca open orders
Alpaca account snapshot
Alpaca position snapshots
```

Never record:

```text
API secret
API key value
database password
full secret-bearing connection URL
```

## 4. SIGTERM / planned shutdown

Expected sequence:

```text
SIGTERM
  |
  v
DRAINING
  |
  v
block new submit
  |
  v
wait bounded active submissions
  |
  v
stop trade_updates stream
  |
  v
STOPPED
```

Check metrics:

```text
runtime_shutdown_attempts
runtime_graceful_shutdowns
runtime_forced_shutdowns
trading_ready
```

A forced shutdown is not equivalent to data loss. Restart reconciliation is still mandatory.

## 5. PostgreSQL unavailable

Symptoms:

```text
startup readiness FAIL
database probe unhealthy
transaction exceptions
trade_update processing failures
```

Actions:

```text
1. close new order admission
2. do not process provider facts without durable persistence
3. keep provider account observable manually if necessary
4. restore PostgreSQL
5. verify migrations
6. restart PyTradeKit
7. run complete two-pass reconciliation
8. verify Inbox
9. require TRADING_READY
```

Never keep trading while durable state is unavailable.

## 6. Alpaca read 429

Expected semantics:

```text
READ 429
-> ProviderRateLimitError
```

Actions:

```text
1. do not alter local economic state
2. wait for a later bounded reconciliation attempt
3. inspect request rate
4. retain NOT_READY if startup convergence cannot complete
```

## 7. Alpaca write 429 or 5xx

Expected semantics:

```text
SUBMIT/CANCEL 429 or 5xx
-> ProviderUncertainOutcomeError
-> UNCERTAIN
```

Actions:

```text
1. never repeat the economic write blindly
2. reconcile using client_order_id or provider order ID
3. inspect open orders and trade_updates
4. apply only provider facts that can be proven
```

## 8. Connection reset during submit

Treat as:

```text
UNCERTAIN
```

Recovery key:

```text
client_order_id
```

Required query:

```text
get_order_by_client_id
```

A 404 at one point in time does not authorize a resubmit.

## 9. trade_updates disconnect

A reconnect is transport recovery only.

Required sequence after reconnect:

```text
stream connected/authenticated
        |
        v
REST account/position/order reconciliation
        |
        v
Inbox inspection
        |
        v
TRADING_READY only if clean
```

## 10. Unknown remote open order

Symptom:

```text
Alpaca OPEN order
+
no durable local Order
```

Runtime response:

```text
NOT_READY
```

Actions:

```text
1. identify whether the order was manual or from another process
2. do not auto-cancel
3. capture provider order ID and client_order_id
4. determine ownership
5. close or import through an explicit operator procedure
6. rerun reconciliation
```

For 0.5, use a dedicated PAPER account.

## 11. Local active order missing at Alpaca

Symptom:

```text
local SUBMITTED/ACCEPTED/CANCEL_REQUESTED
provider query -> 404
```

Response:

```text
NOT_READY
```

Actions:

```text
1. query by both external_order_id and client_order_id when available
2. inspect closed orders in Alpaca UI/API
3. inspect trade_updates evidence
4. do not resubmit
5. resolve manually if provider evidence remains ambiguous
```

## 12. Provider fill quantity greater than local quantity

Symptom:

```text
provider filled_qty > durable local filled_quantity
```

Response:

```text
NOT_READY
```

Reason:

```text
order snapshot is insufficient to reconstruct individual executions
```

Required evidence:

```text
execution_id
quantity
price
timestamp
```

Do not create a synthetic average-price Fill.

## 13. Position mismatch

Any of these block readiness:

```text
provider position missing locally
local non-flat position missing remotely
quantity mismatch
average-price mismatch
unmapped provider asset
```

Actions:

```text
1. stop new submissions
2. inspect persisted Fills
3. inspect processed-fill registry
4. inspect Inbox
5. inspect provider trade activity
6. repair only with explicit economic evidence
```

## 14. Cash mismatch

If local Balance already exists:

```text
local cash != provider cash
```

then:

```text
NOT_READY
```

Do not overwrite the local ledger automatically.

Investigate:

```text
missing fill
fee
manual activity
external transfer
qualification trade
wrong account
stale database
```

## 15. Unprocessed Inbox record

An Inbox record not in `PROCESSED` means a provider fact may not have completed its local transaction.

Actions:

```text
1. keep NOT_READY
2. inspect event identity and payload hash
3. verify local Order/Fill/Portfolio state
4. replay the provider fact only through the normal idempotent processor
5. verify Inbox -> PROCESSED
```

## 16. Pending Outbox record

Pending Outbox is different from pending Inbox.

```text
business transaction committed
Outbox pending publication
```

This does not itself block trading readiness.

Actions:

```text
1. repair publisher
2. dispatch pending Outbox at least once
3. rely on consumer idempotency
```

## 17. Crash before COMMIT

Expected state:

```text
Inbox claim rolled back
Fill rolled back
Order mutation rolled back
Portfolio mutation rolled back
Outbox rolled back
```

The event may be replayed.

## 18. Crash after COMMIT

Expected state:

```text
Inbox PROCESSED
Fill durable
Order durable
Portfolio durable
Outbox durable
```

A replay must be detected as duplicate.

## 19. Forced shutdown

Metric:

```text
runtime_forced_shutdowns > 0
```

Actions:

```text
1. restart with admission closed
2. complete LOT-09 reconciliation
3. inspect Inbox
4. inspect open orders
5. require TRADING_READY
```

## 20. Operational evidence paths

Recommended:

```text
artifacts/runtime/operational-events.jsonl
artifacts/qualification/v050-paper.json
artifacts/qualification/readiness.json
```

Do not commit credential-bearing `.env` files.

## 21. Recovery exit criteria

Incident may be closed only when:

```text
database healthy
provider account identity verified
positions converged
orders converged
unknown open orders = 0
stream authenticated
post-stream reconciliation clean
unprocessed Alpaca Inbox = 0
TradingReadinessReport.trading_ready = true
```

## 22. Escalation

Stop automated recovery and require manual investigation when:

```text
provider state cannot be proven
unexpected remote order exists
position mismatch persists
filled state lacks execution facts
account identity differs
cleanup position differs from baseline
```

## 23. Final operating principle

> Availability is secondary to economic correctness. When evidence is incomplete, PyTradeKit must remain NOT_READY rather than guess.
