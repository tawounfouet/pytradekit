# 51 - PyTradeKit - LOT-09 Startup, Restart & End-to-End Reconciliation

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-09 - Startup, Restart & End-to-End Reconciliation`  
**Date :** 2026-10-22  
**Statut :** Implementation  
**Precedents :** LOT-01 a LOT-08  
**Provider :** Alpaca PAPER  
**SDK gele :** `alpaca-py==0.44.0`

---

## 1. Objectif

LOT-09 assemble pour la premiere fois l'ensemble du vertical slice PyTradeKit 0.5.

Avant LOT-09, les briques existaient separement :

```text
PostgreSQL
UnitOfWork
Inbox
Outbox
Alpaca runtime configuration
Alpaca ACL
ExecutionPort adapter
Market data
Account snapshots
Position snapshots
```

LOT-09 les transforme en un runtime coherent.

La sequence cible devient :

```text
START
  |
  v
LOT-05 startup prerequisites
  |
  v
load provider account + positions
  |
  v
load durable local orders + portfolio
  |
  v
reconcile local/provider state
  |
  v
load all Alpaca open orders
  |
  v
verify account-wide order convergence
  |
  v
start authenticated trade_updates
  |
  v
run a second reconciliation pass
  |
  v
verify Inbox gaps
  |
  v
TRADING_READY
```

---

## 2. Pourquoi LOT-09 est different

Les lots precedents qualifiaient des composants.

LOT-09 qualifie une propriete systeme :

```text
restart does not duplicate economic effects
```

et une deuxieme propriete :

```text
TRADING_READY means local durable state
and provider state are known to have converged
```

---

## 3. Principe fondamental

Le runtime ne devient jamais trading-ready parce que :

```text
database is reachable
AND
provider authentication works
```

Il devient trading-ready uniquement si :

```text
configuration safe
+
database ready
+
provider account verified
+
portfolio converged
+
orders converged
+
remote open-order inventory converged
+
private stream authenticated
+
post-stream reconciliation clean
+
Inbox clean
```

---

## 4. Trois niveaux de readiness

PyTradeKit distingue maintenant :

```text
NOT_READY
READY_FOR_STARTUP
TRADING_READY
```

### READY_FOR_STARTUP

LOT-05.

Signifie :

```text
profile valid
PAPER hard lock valid
secrets resolved
PostgreSQL reachable
account identity valid
market clock reachable
```

### TRADING_READY

LOT-09.

Signifie en plus :

```text
durable economic state converged
private provider facts subscribed
race window closed
no unresolved Inbox fact
```

---

## 5. Nouveau modele TradingReadinessReport

Le runtime introduit :

```text
TradingReadinessReport
```

avec :

```text
provider
environment
masked account
checks
gaps
state
trading_ready
```

State :

```text
TRADING_READY
NOT_READY
```

---

## 6. Fail closed

La regle est :

```text
one unresolved economic gap
=> NOT_READY
```

Aucun warning economique n'est automatiquement transforme en PASS.

---

## 7. Full runtime composition

LOT-09 introduit :

```text
AlpacaPaperRuntimeSystem
```

construit par :

```python
build_alpaca_paper_runtime_system(...)
```

Il assemble :

```text
LOT-05 AlpacaPaperRuntimeComposition
        |
        +-- TradingClient read
        +-- single-attempt command client
        +-- market data client
        +-- private TradingStream
        +-- PostgreSQL SessionFactory
        |
        v
StaticAlpacaReferenceResolver
        |
        +-- AlpacaExecutionAdapter
        +-- AlpacaMarketDataSnapshots
        +-- AlpacaOrderStateReader
        +-- AlpacaOpenOrderInventory
        +-- AlpacaTradeUpdateProcessor
        +-- AlpacaTradeUpdateStreamRunner
        |
        v
AlpacaStartupCoordinator
```

---

## 8. Canonical AccountId remains explicit

LOT-09 ne derive jamais le `AccountId` canonique depuis l'UUID Alpaca.

Le builder exige :

```text
AccountId canonical
```

en entree.

L'identite Alpaca reste :

```text
external account identity
```

---

## 9. Instrument mappings remain explicit

Le runtime system exige aussi :

```text
Iterable[InstrumentMapping]
```

Ces mappings alimentent le resolver bidirectionnel LOT-08.

Aucun symbole Alpaca ne devient automatiquement un `InstrumentId`.

---

## 10. Private stream added to composition

LOT-05 construit maintenant aussi :

```text
AlpacaPaperTradeStream
```

avec :

```text
paper=True
```

Il n'existe aucun selector LIVE dans LOT-09.

---

## 11. Authenticated stream readiness

`TradingStream.run()` ne suffit pas pour declarer le stream ready.

LOT-09 etend le stream provider avec un signal :

```text
connected
+
authenticated
+
trade_updates subscribed
=> provider stream ready
```

---

## 12. Pourquoi le simple thread alive ne suffit pas

Un thread peut etre actif pendant :

```text
DNS failure
connect retry
authentication failure
reconnect loop
```

Le runtime attend donc un signal apres :

```text
_start_ws()
```

et non simplement apres :

```text
Thread.start()
```

---

## 13. AlpacaTradeUpdateStreamRunner

Le runner :

```text
subscribe handler
start daemon thread
run TradingStream
wait authenticated readiness
```

Il expose :

```text
start()
stop()
running
```

---

## 14. Event ordering

Le handler stream est async.

Le processing local PostgreSQL est sync.

LOT-09 utilise :

```python
await asyncio.to_thread(handler, update)
```

mais attend la fin du handler avant de retourner au dispatch.

Ainsi :

```text
trade_update N
processed before
trade_update N+1 dispatch completion
```

dans ce consumer.

---

## 15. Reconnect is not reconciliation

Le SDK peut reconnecter le WebSocket.

Mais :

```text
websocket reconnect
!=
economic state recovery
```

LOT-09 conserve donc la regle du freeze 46 :

```text
reconnect
then
snapshot/query reconciliation
```

---

## 16. Two-phase startup reconciliation

Le runtime utilise deux cycles.

### Phase A - before stream

```text
provider snapshots
+
durable local state
+
order inventory
=> converge
```

Si un gap existe :

```text
stream is not required to declare failure
NOT_READY
```

### Phase B - after stream

Apres authentication du stream :

```text
run the same reconciliation cycle again
```

---

## 17. Pourquoi deux passages

Il existe une fenetre classique :

```text
snapshot read
        |
        | provider changes here
        v
stream subscription
```

Un ordre peut etre rempli dans cette fenetre.

Le second passage detecte cette divergence.

---

## 18. Race-window rule

Sequence :

```text
snapshot A
reconcile A
start stream
snapshot B
reconcile B
TRADING_READY
```

et non :

```text
snapshot
start stream
TRADING_READY
```

---

## 19. Durable order reconciliation queries

Les repositories Order disposent maintenant de :

```text
get_by_client_order_id()
get_by_external_order_id()
list_reconcilable()
```

---

## 20. list_reconcilable

Cette query retourne :

```text
non-terminal orders
OR
execution_certainty == UNCERTAIN
```

en ordre stable :

```text
created_at
id
```

---

## 21. Pourquoi les ordres actifs restent reconcilables

Un ordre :

```text
ACCEPTED
```

reste un effet economique distant actif.

Il doit donc etre revalide au restart.

---

## 22. Pre-submission durable states

Si le restart trouve :

```text
CREATED
VALIDATED
```

LOT-09 ne submit jamais automatiquement.

Il produit un gap :

```text
operator decision required
```

---

## 23. Raison

Le runtime ne sait pas si le crash a eu lieu :

```text
before provider submit
```

ou si un futur code a pu produire un effet hors transaction.

Regle :

```text
restart never invents a new economic command
```

---

## 24. SUBMITTED + UNCERTAIN

Cas central :

```text
local:
SUBMITTED
UNCERTAIN

provider:
ACCEPTED
```

LOT-09 produit :

```text
ExecutionReport ACCEPTED
```

et applique :

```text
Order.accept()
```

dans PostgreSQL.

---

## 25. Reconciliation Outbox

Cette convergence durable produit :

```text
OrderReconciled
```

dans l'Outbox.

La mutation locale et son event sont commites dans la meme UnitOfWork.

---

## 26. Restart idempotence

Au restart suivant :

```text
local ACCEPTED
provider ACCEPTED
```

ne produit aucune nouvelle mutation.

Donc :

```text
one convergence
=> one OrderReconciled Outbox record
```

dans le scenario qualifie.

---

## 27. Provider state reader

LOT-09 introduit :

```text
AlpacaOrderStateReader
```

Resolution :

```text
external_order_id known
-> get_order_by_id()

else
-> get_order_by_client_id()
```

---

## 28. Provider 404

Un 404 signifie :

```text
not observable now
```

et non :

```text
safe to resubmit
```

Le resultat :

```text
None
```

devient un reconciliation gap.

---

## 29. Partial fill restart semantics

Un snapshot ordre Alpaca peut contenir :

```text
filled_qty
filled_avg_price
```

sans execution IDs individuels.

LOT-09 applique la regle LOT-06/07 :

```text
never synthesize Fill
```

---

## 30. Partial fill already known locally

Si :

```text
local PARTIALLY_FILLED qty = X
provider PARTIALLY_FILLED qty = X
```

et qu'aucun cancel n'est pending :

```text
converged
```

Le runtime n'a pas besoin de recreer les fills deja durables.

---

## 31. Partial fill local behind

Si :

```text
provider filled_qty > local filled_quantity
```

le runtime bloque :

```text
missing execution facts
=> NOT_READY
```

---

## 32. Why block

Sans execution ID, le runtime ne peut pas garantir :

```text
Fill idempotency
individual price
portfolio effect
audit trail
```

---

## 33. Cancel reconciliation

Provider `CANCELED` n'est applique automatiquement que si le local indique un vrai cancel workflow :

```text
CANCEL_REQUESTED
```

ou :

```text
PARTIALLY_FILLED
+
cancel_requested = true
```

---

## 34. Unsolicited provider cancel

Si :

```text
local ACCEPTED
provider CANCELED
```

sans demande locale :

```text
gap
```

Le Domain n'est pas etendu silencieusement.

---

## 35. Expiration

`EXPIRED` peut etre applique via `ExecutionReport` aux etats actifs autorises par le Domain.

---

## 36. Rejection

Provider `REJECTED` est applique automatiquement seulement lorsque le local est encore :

```text
SUBMITTED
```

Une rejection apres acceptance constitue une divergence.

---

## 37. Remote open-order inventory

LOT-09 interroge aussi :

```text
get_orders(
    status=OPEN,
    limit=500
)
```

---

## 38. Why account-wide order inventory

Reconciler uniquement les ordres locaux ne detecte pas :

```text
remote order exists
local database has no order
```

Ce cas peut arriver apres :

```text
manual provider operation
state loss
wrong database
wrong account reuse
```

---

## 39. Dedicated PAPER account rule

Pour PyTradeKit 0.5, le compte PAPER est traite comme un compte dedie.

Donc :

```text
every open Alpaca order
must have a durable local match
```

---

## 40. Unknown remote order

Si un ordre open Alpaca n'a pas de correspondance locale :

```text
NOT_READY
```

Le runtime ne l'annule pas automatiquement.

---

## 41. Terminal local / open remote

Si :

```text
local terminal
provider open
```

alors :

```text
NOT_READY
```

---

## 42. Provider ID mismatch

Si le meme client reference pointe vers un autre provider order ID :

```text
NOT_READY
```

La provider identity ne peut pas changer silencieusement.

---

## 43. Account reconciliation

Le snapshot LOT-08 est relu a chaque cycle.

Le canonical `AccountId` doit correspondre au runtime system.

---

## 44. Initial account bootstrap

Si aucun Account local n'existe :

```text
ProviderAccountSnapshot.account
```

peut initialiser l'account canonique deja choisi par configuration.

Le provider ne choisit pas son ID canonique.

---

## 45. Initial cash bootstrap

Si aucun Balance local n'existe pour la devise du compte :

```text
cash provider
```

initialise le Balance durable.

---

## 46. Cash mismatch after bootstrap

Si un Balance local existe et que :

```text
local cash != provider cash
```

LOT-09 bloque readiness.

Il n'ecrase pas automatiquement le ledger local.

---

## 47. Position convergence

Pour chaque provider position :

```text
provider Instrument
-> reverse InstrumentMapping
-> canonical InstrumentId
-> local Position
```

---

## 48. Provider position without local position

Ce cas produit :

```text
NOT_READY
```

LOT-09 ne cree pas automatiquement une Position avec :

```text
realized_pnl = 0
```

car cette valeur serait inventee.

---

## 49. Quantity mismatch

```text
local quantity != provider signed_quantity
=> NOT_READY
```

---

## 50. Average price mismatch

```text
local average_price != provider average_price
=> NOT_READY
```

---

## 51. Local non-flat position missing remotely

```text
local quantity != 0
AND
provider has no position
=> NOT_READY
```

---

## 52. Flat local positions

Une Position locale flat peut ne pas apparaitre dans :

```text
get_all_positions()
```

sans constituer un gap.

---

## 53. TradeUpdate transaction

Le coeur du LOT est :

```text
AlpacaTradeUpdateProcessor
```

---

## 54. Transaction sequence

Pour chaque `trade_update` :

```text
BEGIN PostgreSQL transaction
        |
        v
Inbox claim
        |
        v
resolve durable local Order
        |
        v
map provider event
        |
        +-- transient -> no canonical report
        |
        +-- canonical report
                |
                +-- durable Fill if present
                |
                +-- apply OMS lifecycle
                |
                +-- apply Portfolio effect
                |
                +-- add Outbox
        |
        v
Inbox PROCESSED
        |
        v
COMMIT
```

---

## 55. Atomicity

Les operations suivantes partagent la meme SQLAlchemy Session :

```text
Inbox
Order
Fill
Position
Balance
ProcessedFillRegistry
Outbox
```

---

## 56. Crash before commit

Si le process crash avant commit :

```text
Inbox claim rolls back
Fill rolls back
Order mutation rolls back
Portfolio mutation rolls back
Outbox rolls back
```

L'evenement peut etre rejoue.

---

## 57. Crash after commit

Si le crash intervient apres commit :

```text
Inbox == PROCESSED
```

Le replay est detecte comme duplicate.

---

## 58. Fill identity

Pour un fill :

```text
external_event_id = fill:<execution_id>
```

Donc le provider execution ID devient aussi la cle Inbox stable du fait economique.

---

## 59. Non-fill event identity

Certains `trade_updates` n'ont pas d'event ID provider stable.

LOT-09 utilise alors un semantic fingerprint SHA-256 fonde sur :

```text
provider order id
client_order_id
event
timestamp
provider order status
filled quantity
```

---

## 60. Important semantic limitation

Cette cle ne pretend pas fournir :

```text
provider-native exactly once delivery
```

Elle fournit :

```text
stable local semantic deduplication
```

Le vrai invariant reste la convergence d'etat.

---

## 61. Payload hash

L'Inbox conserve aussi :

```text
SHA-256
```

du payload JSON canonique du TradeUpdate.

---

## 62. Unknown event local order

Si un `trade_update` ne peut pas etre relie a un Order durable :

```text
ProviderStateReconciliationRequired
```

La transaction rollback.

Le claim Inbox n'est donc pas perdu comme faux processed.

---

## 63. Local order resolution for stream facts

Resolution :

```text
client_order_id first
external_order_id second
```

Le client reference reste la recovery key principale.

---

## 64. Fill persistence

Avant l'effet Portfolio :

```text
FillRepository.contains_external()
```

protege la persistence immutable.

Puis :

```text
FillRepository.add()
```

si l'execution n'existe pas.

---

## 65. OMS application

Le canonical `ExecutionReport` traverse :

```text
HandleExecutionReport
```

La couche provider ne mute pas directement Order.

---

## 66. Portfolio application

Les fills traversent :

```text
OrdersPortfolioEffectAdapter
    |
    v
ApplyFillToPortfolio
```

avec les repositories de la meme UnitOfWork.

---

## 67. Portfolio dedup

La protection locale repose aussi sur :

```text
ProcessedFillRegistry
```

Donc le systeme possede plusieurs barrieres complementaires :

```text
Inbox external event
Fill external identity
Order processed fill IDs
Portfolio ProcessedFillRegistry
```

---

## 68. Outbox

Chaque canonical ExecutionReport applique produit :

```text
ExecutionReportApplied
```

dans l'Outbox.

---

## 69. Outbox payload

Il contient uniquement des valeurs serialisables et provider-neutral :

```text
order_id
status
external_order_id
fill_id
external_fill_id
fill_quantity
fill_price
fill_currency
```

Les Decimal sont serialises en string.

---

## 70. Outbox dispatch semantics

LOT-09 ne bloque pas `TRADING_READY` parce qu'un Outbox record attend publication.

Pourquoi :

```text
business transaction is already durable
```

et l'Outbox garantit :

```text
at-least-once later dispatch
```

---

## 71. Inbox does block readiness

Un Inbox record durable non PROCESSED indique au contraire :

```text
provider fact not fully applied
```

Donc :

```text
unprocessed Inbox
=> NOT_READY
```

---

## 72. list_unprocessed

Le PostgresInboxRepository ajoute :

```text
list_unprocessed(provider, limit)
```

pour le gate de restart.

---

## 73. Stream starts only after clean first pass

Si la premiere reconciliation detecte :

```text
position mismatch
missing provider order
unknown remote order
missing execution facts
```

le coordinator retourne :

```text
NOT_READY
```

sans declarer le runtime operationnel.

---

## 74. Stream authenticated then second pass

Si le premier pass est clean :

```text
start trade_updates
wait provider ready
run reconciliation again
```

---

## 75. Post-stream gap

Si le second pass detecte un gap :

```text
NOT_READY
```

Le stream peut rester actif comme voie d'observation, mais aucune admission trading ne doit etre autorisee.

---

## 76. Admission contract

Le code qui autorisera les strategies a envoyer de nouveaux ordres doit utiliser :

```text
TradingReadinessReport.trading_ready
```

et non :

```text
StartupReadinessReport.ready_for_startup
```

---

## 77. Restart example

### Before crash

```text
local order:
SUBMITTED
UNCERTAIN

provider:
order accepted
```

### Restart

```text
load order
query by client_order_id
provider ACCEPTED
apply ExecutionReport
persist Order ACCEPTED
write OrderReconciled
```

### Second restart

```text
local ACCEPTED
provider ACCEPTED
no new mutation
no duplicate OrderReconciled
```

---

## 78. Fill replay example

First delivery :

```text
execution_id = E1

Inbox claim E1
Fill E1 inserted
Order filled
Portfolio updated
Outbox inserted
Inbox processed
COMMIT
```

Replay :

```text
Inbox claim E1 -> false
return duplicate
```

Result :

```text
1 Fill
1 economic effect
1 Outbox
```

---

## 79. PostgreSQL E2E qualification

LOT-09 ajoute un scenario d'integration avec PostgreSQL reel.

Il prouve :

```text
UNCERTAIN -> ACCEPTED convergence
restart idempotence
trade_update replay idempotence
Fill durability
Order durability
Portfolio durability
Inbox durability
Outbox durability
```

---

## 80. No real Alpaca dependency in E2E CI

Les tests E2E utilisent :

```text
real PostgreSQL
fake deterministic provider observations
```

Cela rend le test :

```text
repeatable
offline
fault-controllable
```

---

## 81. Real PAPER remains a release gate

La CI locale ne remplace toujours pas :

```text
real Alpaca PAPER qualification
```

LOT-10 devra executer le systeme avec :

```text
real account
real stream
real MARKET/LIMIT/CANCEL
real restart
real provider observations
```

---

## 82. New runtime system builder

Usage conceptuel :

```python
composition = build_alpaca_paper_runtime(profile, secrets)

system = build_alpaca_paper_runtime_system(
    composition=composition,
    mappings=mappings,
    account_id=account_id,
    clock=clock,
)

readiness = system.start()

if not readiness.trading_ready:
    refuse_new_orders()
```

---

## 83. Stop

Le systeme expose :

```python
system.stop()
```

pour stopper le private stream.

---

## 84. Shutdown scope

LOT-09 fournit le stop du stream.

Le shutdown production complet avec :

```text
signal handling
admission drain
outbox flush policy
metrics finalization
```

peut etre renforce dans LOT-10.

---

## 85. No automatic economic repair

LOT-09 ne fait jamais :

```text
auto submit missing order
auto cancel unknown remote order
auto recreate missing fills
auto flatten unexpected position
auto overwrite mismatched position
```

---

## 86. Reconciliation philosophy

La reconciliation separe trois categories.

### Safe local convergence

Exemple :

```text
SUBMITTED UNCERTAIN
provider ACCEPTED
```

Peut etre applique automatiquement.

### Already converged

Exemple :

```text
local ACCEPTED
provider ACCEPTED
```

No-op.

### Missing economic evidence

Exemple :

```text
provider filled_qty > local
```

Bloque readiness.

---

## 87. Why conservative recovery

Dans un trading system :

```text
false recovery
```

peut produire un effet economique duplique.

Un :

```text
NOT_READY
```

explicite est donc preferable a une conjecture automatique.

---

## 88. Dedicated account constraint

Le gate strict sur les open orders implique pour 0.5 :

```text
Alpaca PAPER account dedicated to PyTradeKit qualification
```

Si l'utilisateur place manuellement un ordre sur ce compte :

```text
startup will detect it
NOT_READY
```

---

## 89. Why this is intentional

Cela evite que PyTradeKit calcule son risque en ignorant :

```text
manual open order
```

sur le meme compte.

---

## 90. Persistence changes

Aucune nouvelle table n'est necessaire.

LOT-09 reutilise :

```text
orders.orders
execution.fills
portfolio.accounts
portfolio.positions
portfolio.balances
portfolio.processed_fills
runtime.inbox
runtime.outbox
```

---

## 91. No migration

LOT-09 ajoute des queries repository mais ne modifie pas le schema.

Donc :

```text
Alembic migration
NOT REQUIRED
```

---

## 92. Order repository additions

Postgres et in-memory supportent maintenant :

```text
get_by_client_order_id
get_by_external_order_id
list_reconcilable
```

---

## 93. Stable order scan

`list_reconcilable()` est trie pour rendre :

```text
tests deterministic
logs deterministic
reconciliation deterministic
```

---

## 94. Message repository addition

```text
PostgresInboxRepository.list_unprocessed()
```

n'ajoute aucune nouvelle persistence semantics.

Il expose l'etat deja present.

---

## 95. Error behavior

Les read errors provider continuent d'utiliser LOT-06 :

```text
translate_alpaca_error(READ)
```

---

## 96. 404 order query

```text
404
-> None
-> reconciliation gap
```

---

## 97. 429 / 5xx read

```text
429
-> ProviderRateLimitError

5xx
-> ProviderUnavailableError
```

Startup ne declare pas TRADING_READY.

---

## 98. Stream auth failure

Si le private stream ne devient pas ready dans la fenetre bornee :

```text
trade_updates_stream FAIL
NOT_READY
```

---

## 99. No hidden LIVE path

Le private stream est construit :

```python
TradingStream(
    ...,
    paper=True,
)
```

La CI verifie l'absence de :

```text
paper=False
TRADING_STREAM_LIVE
```

dans LOT-09.

---

## 100. Architecture gates

Les fitness functions verifient :

```text
startup has no submit
startup has no cancel
stream processing has no economic command transport
private stream PAPER only
post-stream reconciliation happens after stream start
runtime composition includes private stream
```

---

## 101. Transaction architecture gate

La CI verifie la presence de :

```text
Inbox claim
Fill add
HandleExecutionReport
ApplyFillToPortfolio
Outbox add
Inbox mark_processed
commit
```

dans le processing pipeline.

---

## 102. Important distinction

Cette fitness function ne remplace pas le test d'integration transactionnel.

Elle empeche surtout une refactorisation accidentelle qui retirerait une etape majeure.

---

## 103. Runtime state after LOT-09

Le systeme dispose maintenant de :

```text
safe configuration
durable state
safe commands
canonical provider observations
restart reconciliation
private event processing
full trading readiness
```

---

## 104. What remains for LOT-10

LOT-10 doit qualifier :

```text
real Alpaca PAPER account
real PostgreSQL
real private stream
controlled orders
process restart
network faults
stream disconnect/reconnect
provider 429/5xx behavior
SIGTERM
crash windows
metrics
logging
runbooks
release gates
```

---

## 105. Fault scenarios for LOT-10

Minimum recommande :

```text
crash before provider submit
response loss after provider accept
crash after provider accept before local update
crash after Inbox claim before commit
crash after local commit before Outbox publish
stream disconnect during partial fill
PostgreSQL unavailable
provider unavailable
restart with unexpected remote order
restart with unexpected remote position
```

---

## 106. Current confidence boundary

Apres LOT-09 :

```text
architecture qualified       YES
code qualified               pending CI
PostgreSQL E2E qualified     pending CI
real PAPER qualified         NO
LIVE qualified               OUT OF SCOPE
```

---

## 107. Expected CI gate

Le lot doit passer :

```text
Typography
Ruff
mypy strict
Import architecture
Architecture/public contracts
Unit/property/integration tests
PostgreSQL qualification
Release artifact qualification
```

---

## 108. No em dash convention

Tous les fichiers LOT-09 respectent la convention projet :

```text
ASCII hyphen-minus only
```

---

## 109. Runtime invariant summary

```text
no blind resubmit
no blind cancel
no synthetic fill
no synthetic position repair
no provider ID as canonical ID
no trading before reconciliation
no duplicate local fill effect
no LIVE fallback
```

---

## 110. Startup summary

```text
LOT-05 READY_FOR_STARTUP
        |
        v
portfolio snapshot
        |
        v
local order scan
        |
        v
provider order queries
        |
        v
open-order inventory
        |
        v
pre-stream convergence
        |
        v
private stream authenticated
        |
        v
post-stream convergence
        |
        v
Inbox clean
        |
        v
TRADING_READY
```

---

## 111. Restart summary

```text
restart
    |
    v
read durable truth
    |
    v
read provider truth
    |
    v
apply only provable facts
    |
    v
block on missing evidence
```

---

## 112. Event summary

```text
trade_update
    |
    v
Inbox
    |
    v
ACL
    |
    v
ExecutionReport
    |
    +-- Fill repository
    +-- OMS
    +-- Portfolio
    +-- Outbox
    |
    v
Inbox PROCESSED
```

---

## 113. Resultat LOT-09

```text
Startup orchestration                  YES
Restart reconciliation                 YES
Two-phase race-window closure          YES
Private trade_updates runtime          YES
Transactional Inbox processing         YES
Durable Fill processing                YES
Transactional OMS + Portfolio          YES
Transactional Outbox                   YES
Remote open-order inventory            YES
Account convergence                    YES
Position convergence                   YES
TradingReadinessReport                 YES
Full runtime system builder            YES
Real PAPER qualification               LOT-10
```

---

## 114. Milestone status

```text
LOT-01 Persistence Contracts                 DONE
LOT-02 PostgreSQL + Migrations               DONE
LOT-03 UnitOfWork + Outbox + Inbox           DONE
LOT-04 Provider Discovery                    DONE
LOT-05 PAPER Runtime Configuration           DONE
LOT-06 Alpaca Anti-Corruption Layer          DONE
LOT-07 Alpaca Execution                      DONE
LOT-08 Alpaca Market Data & Snapshots        DONE
LOT-09 Startup, Restart & E2E Reconciliation IMPLEMENTED

LOT-10 Production Qualification              NEXT
```

---

## 115. Final principle

> Recovery never creates economic truth. It compares durable local facts with provider facts, applies only evidence that is safe to prove, and blocks trading whenever the remaining gap cannot be reconciled without guessing.
