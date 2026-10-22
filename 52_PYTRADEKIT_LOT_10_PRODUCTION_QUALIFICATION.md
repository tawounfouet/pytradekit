# 52 - PyTradeKit - LOT-10 Production Qualification

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-10 - Production Qualification`  
**Date :** 2026-10-22  
**Statut :** CI qualified - real PAPER evidence pending  
**Provider :** Alpaca PAPER  
**SDK gele :** `alpaca-py==0.44.0`  
**LIVE :** out of scope

---

## 1. Objectif

LOT-10 ne cherche plus principalement a construire des primitives de trading.

Il cherche a prouver que l'assemblage construit entre LOT-01 et LOT-09 se comporte correctement lorsque l'environnement devient hostile.

Les categories de qualification sont :

```text
process crash
restart
network uncertainty
provider 429
provider 5xx
database failure
private stream failure
SIGTERM
shutdown drain
duplicate delivery
post-commit replay
observability
operator response
real Alpaca PAPER
release decision
```

---

## 2. Changement de nature

Les lots 01 a 09 construisent le systeme.

LOT-10 tente de le casser.

La question n'est plus :

```text
Can PyTradeKit submit an order?
```

La question devient :

```text
Can PyTradeKit preserve economic correctness
when the process, network, database or provider behaves badly?
```

---

## 3. Qualification layers

LOT-10 separe les preuves en trois niveaux.

### Deterministic code qualification

```text
unit
architecture
fault injection
PostgreSQL integration
```

### Operational qualification

```text
admission
shutdown
metrics
audit events
runbooks
```

### Real provider qualification

```text
real Alpaca PAPER
real authenticated stream
real MARKET
real LIMIT
real CANCEL
real restart
real cleanup
```

---

## 4. CI is necessary but not sufficient

Une CI verte ne suffit jamais a declarer :

```text
v0.5.0 release-ready
```

Elle prouve uniquement les proprietes deterministes.

Le release gate exige aussi des preuves du provider reel PAPER.

---

## 5. New production operational shell

LOT-10 ajoute :

```text
RuntimeAdmissionGate
AdmissionControlledExecutionPort
ProductionRuntimeSupervisor
QualifiedAlpacaPaperRuntime
```

---

## 6. Runtime lifecycle

Etats :

```text
STARTING
READY
DEGRADED
DRAINING
STOPPED
```

---

## 7. Submission admission

Nouveaux submits :

```text
allowed only when READY
```

Donc :

```text
STARTING -> blocked
DEGRADED -> blocked
DRAINING -> blocked
STOPPED -> blocked
```

---

## 8. Cancellation during shutdown

La cancellation est un mecanisme de reduction de risque.

Elle reste donc disponible pendant :

```text
READY
DRAINING
```

Elle est bloquee pendant :

```text
STARTING
DEGRADED
STOPPED
```

---

## 9. Query during shutdown

Les queries de reconciliation restent possibles jusqu'a :

```text
STOPPED
```

Cela permet au runtime de continuer a observer l'etat provider pendant le drain.

---

## 10. Active submissions

`RuntimeAdmissionGate` compte :

```text
active_submissions
```

Chaque submit admis prend un slot.

Le slot est libere meme en cas d'exception grace au context manager.

---

## 11. Graceful shutdown

Sequence :

```text
shutdown requested
        |
        v
DRAINING
        |
        v
close new submit admission
        |
        v
wait bounded active submissions
        |
        v
stop runtime stream
        |
        v
STOPPED
```

---

## 12. Bounded drain

Le shutdown ne peut pas attendre indefiniment.

Configuration :

```text
timeout seconds
```

Resultat :

```text
drained = true
```

ou :

```text
forced = true
```

---

## 13. Forced shutdown semantics

Un shutdown force ne pretend pas que les commandes provider ont disparu.

Le restart suivant doit obligatoirement repasser par LOT-09 :

```text
durable state
+
provider state
+
reconciliation
```

---

## 14. SIGTERM

`ProductionRuntimeSupervisor` peut installer des handlers :

```text
SIGTERM
SIGINT
```

Ils utilisent exactement la meme sequence que :

```python
shutdown()
```

---

## 15. No special signal recovery path

Le signal handler ne contient pas une logique economique alternative.

Il ne :

```text
submit rien
cancel rien automatiquement
liquidate rien
```

---

## 16. Runtime not ready

Si `system.start()` retourne :

```text
trading_ready = false
```

alors :

```text
gate -> DEGRADED
new submit admission -> closed
```

---

## 17. Runtime start exception

Si le startup leve une exception :

```text
gate -> DEGRADED
trading_ready gauge -> 0
runtime_start_failures++
```

L'exception est ensuite propagee.

---

## 18. AdmissionControlledExecutionPort

Le wrapper implemente toujours le meme :

```text
ExecutionPort
```

Il ne change donc pas le contrat consumer-owned.

---

## 19. Submit flow

```text
SubmitOrder
    |
    v
AdmissionControlledExecutionPort
    |
    +-- gate READY?
    |
    v
AlpacaExecutionAdapter
```

---

## 20. Cancel flow

```text
CancelOrder
    |
    v
AdmissionControlledExecutionPort
    |
    +-- READY or DRAINING?
    |
    v
AlpacaExecutionAdapter
```

---

## 21. Fault injection

LOT-10 introduit :

```text
FaultPoint
FaultInjector
NullFaultInjector
OneShotFaultInjector
InjectedRuntimeFault
```

---

## 22. Production default

Le runtime normal utilise :

```text
NullFaultInjector
```

Donc aucun comportement aleatoire ni fault injection n'est actif en production.

---

## 23. Deterministic only

Les faults de qualification sont nommes.

Il n'y a aucun :

```text
random crash
probabilistic exception
sleep-based race simulation
```

dans le core fault injector.

---

## 24. Qualified crash windows

Points :

```text
BEFORE_INBOX_CLAIM
AFTER_INBOX_CLAIM
AFTER_FILL_PERSIST
AFTER_CANONICAL_APPLY
AFTER_OUTBOX_ADD
BEFORE_COMMIT
AFTER_COMMIT
```

---

## 25. BEFORE_INBOX_CLAIM

Failure occurs before any durable event claim.

Expected:

```text
no Inbox
no Fill
no Order mutation
no Portfolio mutation
no Outbox
```

---

## 26. AFTER_INBOX_CLAIM

The Inbox insert exists only inside the open transaction.

Injected crash expected:

```text
transaction rollback
Inbox disappears
```

---

## 27. AFTER_FILL_PERSIST

A Fill may have been flushed to PostgreSQL but not committed.

Crash expected:

```text
Fill rollback
Inbox rollback
all other state unchanged
```

---

## 28. AFTER_CANONICAL_APPLY

At this point:

```text
Order may be mutated
Position may be mutated
Balance may be mutated
ProcessedFillRegistry may be written
```

but all changes remain in the same transaction.

Crash expected:

```text
everything rolls back
```

---

## 29. AFTER_OUTBOX_ADD

The Outbox event may have been flushed.

Crash expected before commit:

```text
Outbox rollback
business state rollback
Inbox rollback
```

---

## 30. BEFORE_COMMIT

This is the last pre-commit crash point.

Expected invariant:

```text
zero new durable economic effect
```

---

## 31. AFTER_COMMIT

This is fundamentally different.

Expected:

```text
Inbox durable
Fill durable
Order durable
Portfolio durable
Outbox durable
```

Then the injected crash occurs.

---

## 32. Replay after AFTER_COMMIT

On restart/replay:

```text
Inbox claim -> false
duplicate -> true
```

No second economic effect is possible.

---

## 33. Crash matrix invariant

For every pre-commit crash point:

```text
first attempt crashes
durable new effects = 0
replay succeeds
durable economic effects = 1
```

For after-commit crash:

```text
first attempt crashes after durable commit
durable economic effects = 1
replay duplicate
durable economic effects remains = 1
```

---

## 34. PostgreSQL real integration

The fault matrix uses real PostgreSQL.

It does not use:

```text
in-memory repository
fake transaction
mock commit
```

---

## 35. Why PostgreSQL matters

The properties depend on actual:

```text
transaction rollback
unique constraints
session flush
savepoint behavior
commit behavior
```

---

## 36. Observability

LOT-10 adds dependency-free observability primitives.

```text
RuntimeMetrics
RuntimeMetricsSnapshot
RuntimeObserver
OperationalEvent
OperationalEventSink
```

---

## 37. Why dependency-free

The 0.5 core does not need to choose:

```text
Prometheus
OpenTelemetry exporter
Datadog
Grafana Cloud
Azure Monitor
```

yet.

The core emits stable operational facts that adapters can export later.

---

## 38. Counters

Examples:

```text
runtime_start_attempts
runtime_start_failures
runtime_ready_transitions
runtime_not_ready
runtime_shutdown_attempts
runtime_graceful_shutdowns
runtime_forced_shutdowns
trade_updates_received
trade_updates_duplicates
trade_updates_applied
trade_updates_transient
trade_updates_failed
```

---

## 39. Gauges

Current baseline:

```text
trading_ready
```

Values:

```text
0
1
```

---

## 40. Metrics snapshot

Metrics are copied into:

```text
RuntimeMetricsSnapshot
```

so callers do not mutate internal metric state.

---

## 41. Structured operational events

Examples:

```text
runtime_starting
runtime_start_failed
runtime_trading_ready
runtime_not_ready
runtime_draining
runtime_stopped
runtime_signal_received
trade_update_failed
```

---

## 42. Secret-safe field policy

Operational event field names containing:

```text
secret
password
api_key
apikey
token
credential
```

are rejected.

---

## 43. JSON Lines sink

LOT-10 provides:

```text
JsonLinesOperationalEventSink
```

Recommended path:

```text
artifacts/runtime/operational-events.jsonl
```

---

## 44. In-memory sink

Tests and local diagnostics use:

```text
InMemoryOperationalEventSink
```

---

## 45. No secret-value introspection

The observer does not inspect arbitrary business payloads.

Runtime code emits only controlled sanitized fields.

---

## 46. Provider rate limits

The frozen LOT-06 semantics are now explicit production gates.

---

## 47. Read 429

```text
READ
429
-> ProviderRateLimitError
```

This is not an economic uncertainty.

---

## 48. Submit 429

```text
SUBMIT
429
-> ProviderUncertainOutcomeError
```

No blind retry.

---

## 49. Read 5xx

```text
READ
503
-> ProviderUnavailableError
```

---

## 50. Submit 5xx

```text
SUBMIT
503
-> ProviderUncertainOutcomeError
```

---

## 51. Transport reset during write

Example:

```text
ConnectionResetError
during CANCEL
```

Expected:

```text
ProviderUncertainOutcomeError
```

---

## 52. Why read/write semantics differ

For a read:

```text
request can be repeated later
```

For an economic write:

```text
provider may have applied the side effect
while the response was lost
```

---

## 53. Real provider harness

LOT-10 adds:

```text
scripts/alpaca_paper_v050_qualification.py
```

---

## 54. PAPER only

The harness has:

```text
no LIVE mode
no paper=False
```

---

## 55. Real order opt-in

Provider writes run only when:

```text
--with-orders
```

is supplied.

---

## 56. Existing acknowledgement still required

The controlled probe requires:

```text
PYTRADEKIT_ALPACA_ORDER_PROBE_ACK
=
I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED
```

---

## 57. Canonical qualification identities

The real runtime harness requires explicit canonical IDs:

```text
PYTRADEKIT_QUALIFICATION_ACCOUNT_ID
PYTRADEKIT_QUALIFICATION_INSTRUMENT_ID
```

The provider does not choose PyTradeKit canonical identity.

---

## 58. Provider asset mapping

During qualification:

```text
explicit canonical InstrumentId
+
configured symbol
+
provider observed Asset.id
```

becomes a temporary explicit `InstrumentMapping`.

---

## 59. Controlled order qualification

With `--with-orders`, existing LOT-45 proof is executed:

```text
MARKET buy
simulated response loss
recovery by client_order_id
LIMIT buy below bid
single cancel
cleanup MARKET sell
```

---

## 60. Recovery proof

Required evidence:

```text
simulated_post_ack_response_loss = true
resubmitted = false
submit_attempts = 1
```

---

## 61. Stream proof

Required:

```text
trade_updates event_count > 0
```

---

## 62. Cleanup proof

Required:

```text
final_position_qty == baseline_position_qty
```

---

## 63. Runtime start/restart proof

The harness builds the real runtime twice against the same PostgreSQL database.

Cycle:

```text
build composition
build LOT-09 system
wrap LOT-10 operational shell
start
require TRADING_READY
shutdown
dispose engine
```

Then a new composition is built again.

---

## 64. Why rebuild composition

This is closer to a real process restart than reusing the same object graph.

It recreates:

```text
SQLAlchemy Engine
SessionFactory
Alpaca clients
TradingStream
reference resolver
startup coordinator
production supervisor
```

---

## 65. Start/restart pass criteria

Both cycles require:

```text
trading_ready = true
shutdown_drained = true
```

---

## 66. Dedicated account requirement

The runtime qualification assumes a dedicated PAPER account.

If an unknown open order exists:

```text
NOT_READY
```

---

## 67. Flat account recommendation

A flat account before qualification minimizes ambiguity.

Unexpected pre-existing positions can intentionally block startup.

---

## 68. CI-qualified flag

The real harness does not assume CI evidence.

It requires explicit:

```text
--ci-qualified
```

to mark deterministic gates PASS in the generated report.

---

## 69. Runbook review flag

Operator runbook review is explicit:

```text
--runbook-reviewed
```

---

## 70. Release evidence model

LOT-10 adds:

```text
QualificationStatus
QualificationGate
ProductionQualificationEvidence
ProductionQualificationReport
```

---

## 71. Qualification statuses

```text
PASS
FAIL
PENDING
```

---

## 72. Release rule

```text
every required gate == PASS
=> release_ready = true
```

Anything else:

```text
release_ready = false
```

---

## 73. Required deterministic gates

```text
ci_quality_gate
postgres_restart_e2e
crash_window_faults
graceful_shutdown
provider_429_5xx_semantics
```

---

## 74. Required real PAPER gates

```text
real_paper_runtime_start_restart
real_paper_market_limit_cancel
real_paper_trade_updates
real_paper_uncertain_recovery
real_paper_cleanup
```

---

## 75. Required operator gate

```text
incident_runbook
```

---

## 76. CI cannot auto-pass real PAPER gates

Default value:

```text
PENDING
```

for every real provider gate.

---

## 77. Final release gate script

LOT-10 adds:

```text
scripts/check_v050_release_gate.py
```

---

## 78. PASS output

```text
PyTradeKit v0.5.0 production qualification gate: PASS
```

Exit code:

```text
0
```

---

## 79. Blocked output

```text
PyTradeKit v0.5.0 production qualification gate: BLOCKED
```

Exit code:

```text
1
```

It also lists:

```text
pending required gates
failed required gates
```

---

## 80. Invalid evidence

Malformed report:

```text
exit code 2
```

---

## 81. CI workflow

LOT-10 adds a visible step:

```text
Production fault qualification
```

---

## 82. Explicit production qualification tests

CI executes:

```text
runtime operations
runtime observability
release qualification
provider fault semantics
PostgreSQL crash windows
LOT-09 restart reconciliation
```

before the complete test suite.

---

## 83. Full suite still runs

The explicit production gate does not replace:

```text
pytest --cov=pytradekit
```

It gives production safety failures their own visible CI step.

---

## 84. SIGTERM unit proof

The supervisor signal handler is tested through:

```text
handle_signal(SIGTERM, None)
```

Expected:

```text
DRAINING
STOPPED
runtime stop called once
```

---

## 85. Drain proof

A test holds one submit inside the admission slot.

Shutdown starts concurrently.

Expected:

```text
new admissions closed
shutdown waits
existing submit returns
runtime stops
forced = false
```

---

## 86. Drain timeout proof

A second test keeps the submit blocked and uses:

```text
timeout = 0
```

Expected:

```text
forced = true
active_submissions_at_timeout = 1
runtime stop still invoked
```

---

## 87. Cancellation during DRAINING proof

Test:

```text
gate READY
begin_draining()
submit -> blocked
cancel -> allowed
```

---

## 88. Observability proof

Tests cover:

```text
counter increment
gauge update
detached snapshot
structured events
JSONL output
secret-like field rejection
```

---

## 89. Fault injection observability

If processing raises:

```text
trade_updates_failed++
trade_update_failed event
```

---

## 90. Duplicate delivery observability

Duplicate Inbox claim:

```text
trade_updates_duplicates++
```

---

## 91. Applied event observability

Canonical report successfully committed:

```text
trade_updates_applied++
```

---

## 92. Transient provider event observability

Mapped transient event:

```text
trade_updates_transient++
```

---

## 93. Runbooks

LOT-10 adds:

```text
docs/runbooks/ALPACA_PAPER_INCIDENT_RESPONSE.md
docs/runbooks/PYTRADEKIT_0_5_RELEASE_QUALIFICATION.md
```

---

## 94. Incident runbook purpose

It covers:

```text
SIGTERM
forced shutdown
PostgreSQL unavailable
read 429
write 429/5xx
connection reset
stream disconnect
unknown remote order
local order missing remotely
fill gap
position mismatch
cash mismatch
Inbox gap
Outbox pending
pre-commit crash
post-commit crash
```

---

## 95. Release runbook purpose

It defines:

```text
account preconditions
environment
acknowledgement
CI proof
real PAPER command
pass criteria
evidence retention
version bump policy
rollback policy
```

---

## 96. Release candidate notes

LOT-10 adds:

```text
docs/releases/0.5.0.md
```

Status:

```text
Release candidate
blocked pending complete real PAPER qualification
```

---

## 97. Version policy

LOT-10 does not automatically bump:

```text
pyproject.toml
```

to `0.5.0`.

---

## 98. Why no automatic version bump

At implementation completion:

```text
code may be qualified
real provider evidence may still be PENDING
```

Creating a final version before the provider proof would weaken the release gate.

---

## 99. Version bump condition

Only after:

```text
check_v050_release_gate.py -> exit 0
```

should the final release process:

```text
set version 0.5.0
finalize release note
merge
tag v0.5.0
publish artifact
```

---

## 100. Real PAPER cannot run in normal CI

The public/default CI does not receive:

```text
Alpaca secrets
explicit order acknowledgement
dedicated account
market-open guarantee
```

This is intentional.

---

## 101. No secret-bearing artifact

The real harness output contains:

```text
masked account
readiness checks
metrics
controlled probe sanitized rows
release gate
```

It does not serialize:

```text
API key
API secret
database URL
database password
```

---

## 102. Market-open constraint

Controlled MARKET qualification requires:

```text
Alpaca market open
```

If closed:

```text
order-writing gates remain PENDING or FAIL
release remains blocked
```

---

## 103. No weakening the probe

LOT-10 does not add an after-hours bypass merely to make the gate green.

---

## 104. Database unavailable behavior

LOT-05 readiness already treats failed database probe as:

```text
NOT READY
```

LOT-10 preserves this.

The production supervisor therefore never opens admission.

---

## 105. Provider unavailable behavior

Startup provider read exceptions propagate.

The production supervisor records:

```text
runtime_start_failures
trading_ready = 0
DEGRADED
```

---

## 106. Private stream unavailable behavior

LOT-09 already requires authenticated stream readiness.

If stream does not become ready:

```text
TRADING_READY = false
```

LOT-10 admission remains closed.

---

## 107. Reconnect behavior

The SDK may reconnect transport.

PyTradeKit still requires reconciliation.

LOT-10 does not change:

```text
connection recovery != state recovery
```

---

## 108. No automatic liquidation

Production shutdown does not call:

```text
close_position
close_all_positions
```

---

## 109. No automatic unknown-order cancel

Qualification/recovery does not cancel unknown remote open orders.

They block readiness.

---

## 110. No new LIVE capability

LOT-10 introduces no:

```text
LIVE enum
LIVE endpoint
paper=False
LIVE CLI flag
```

---

## 111. Architecture gate for real harness

CI asserts the real qualification script contains no LIVE mode.

---

## 112. Architecture gate for release evidence

CI asserts the release model contains all real PAPER gates.

---

## 113. Architecture gate for commit boundaries

CI asserts:

```text
BEFORE_COMMIT
<
uow.commit()
<
AFTER_COMMIT
```

in the trade-update processor.

---

## 114. Architecture gate for admission

CI asserts the operational shell contains:

```text
READY
submission_slot
begin_draining
wait_for_submissions
```

---

## 115. Architecture gate for cancellation

CI asserts DRAINING is represented in the cancel path.

---

## 116. Result after implementation

The codebase now contains:

```text
production admission control
graceful shutdown
signal path
fault injection
runtime metrics
structured events
JSONL audit sink
real PAPER qualification harness
release evidence model
release gate checker
incident runbook
release runbook
release candidate note
explicit CI production gate
```

---

## 117. What implementation completion does not mean

It does not mean:

```text
real PAPER qualification has already been executed
```

No Alpaca credentials are available to this implementation session.

---

## 118. Current evidence state

Deterministic qualification is complete.

GitHub Actions:

```text
run_number = 159
run_id     = 39724152573
head       = f079e0ef9cad637b54398b9e2841fc666931a13d
```

Qualified gates:

```text
Typography                         PASS
Ruff                               PASS
mypy strict                        PASS - 360 source files
Import architecture                PASS
Architecture/public contracts      PASS - 77 tests
Production fault qualification     PASS - 26 tests
Full test suite                    PASS - 396 tests
Release artifact qualification     PASS
```

Release evidence therefore stands at:

```text
ci_quality_gate                    PASS
postgres_restart_e2e              PASS
crash_window_faults               PASS
graceful_shutdown                 PASS
provider_429_5xx_semantics        PASS

real_paper_runtime_start_restart  PENDING
real_paper_market_limit_cancel    PENDING
real_paper_trade_updates          PENDING
real_paper_uncertain_recovery     PENDING
real_paper_cleanup                PENDING
```

---

## 119. Release state at that point

```text
release_ready = false
```

This is the correct result.

---

## 120. Command for final PAPER qualification

When prerequisites are satisfied:

```bash
python scripts/alpaca_paper_v050_qualification.py   --with-orders   --ci-qualified   --runbook-reviewed   --output artifacts/qualification/v050-paper.json
```

---

## 121. Command for final release decision

```bash
python scripts/check_v050_release_gate.py   artifacts/qualification/v050-paper.json
```

---

## 122. Success criteria

Only this combination is sufficient:

```text
deterministic safety PASS
+
real provider safety PASS
+
operator runbook PASS
```

---

## 123. Milestone status

```text
LOT-01 Persistence Contracts                 DONE
LOT-02 PostgreSQL + Migrations               DONE
LOT-03 UnitOfWork + Outbox + Inbox           DONE
LOT-04 Provider Discovery                    DONE
LOT-05 PAPER Runtime Configuration           DONE
LOT-06 Alpaca Anti-Corruption Layer          DONE
LOT-07 Alpaca Execution                      DONE
LOT-08 Alpaca Market Data & Snapshots        DONE
LOT-09 Startup, Restart & E2E Reconciliation DONE
LOT-10 Production Qualification              CI QUALIFIED

v0.5.0 final release                         REAL PAPER GATE PENDING
```

---

## 124. Final principle

> Production qualification is not a promise that failure will never happen. It is evidence that when failure happens, PyTradeKit preserves economic truth, blocks unsafe admission, recovers from durable facts, and refuses to claim readiness without proof.