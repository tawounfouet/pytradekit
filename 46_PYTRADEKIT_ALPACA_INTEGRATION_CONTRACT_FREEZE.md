# 46 - PyTradeKit - Alpaca Integration Contract Freeze

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-04G - Alpaca Integration Contract Freeze`  
**Date :** 2026-10-22  
**Statut :** Contract frozen for LOT-05 implementation - real PAPER evidence remains release-blocking  
**SDK de reference :** `alpaca-py==0.44.0`  
**Provider cible :** Alpaca Trading API + Market Data API  
**Environment cible :** PAPER uniquement

---

## 1. Objet

Ce document fige le contrat d'integration Alpaca qui servira de reference a l'implementation du runtime PyTradeKit 0.5.

Il consolide les preuves et decisions issues de :

```text
39 - Alpaca API & SDK Integration Analysis
43 - Provider Comparative Architecture
44 - Alpaca PAPER Read-Only Probe Harness
45 - Alpaca Controlled PAPER Order Probe
```

Le but du freeze est de mettre fin a la phase de discovery architecturale.

A partir de ce document, LOT-05 et les lots Alpaca suivants ne doivent plus redecider implicitement :

```text
environment
SDK version
scope d'ordres
identity mapping
retry policy
UNCERTAIN policy
status mapping
stream role
snapshot role
reconciliation role
provider boundary
```

Toute modification d'un de ces points devient une modification explicite du contrat.

---

## 2. Resultat du gate

Resultat :

```text
PASS FOR LOT-05 IMPLEMENTATION
```

avec une reserve obligatoire :

```text
REAL PAPER QUALIFICATION
IS STILL REQUIRED
BEFORE v0.5.0 RELEASE
```

Autrement dit :

```text
architecture frozen
code contract frozen
CI contract frozen

but

real provider behavior not yet fully evidenced
until probes 44 and 45 run with real PAPER credentials
```

---

## 3. Ce que signifie "freeze"

Le freeze signifie :

```text
the implementation may now depend on these decisions
```

Il ne signifie pas :

```text
the provider can never evolve
```

Toute evolution future suit :

```text
observe provider change
        |
        v
update discovery evidence
        |
        v
change contract explicitly
        |
        v
update contract tests
        |
        v
requalify PAPER
```

---

## 4. Sources de decision

Ordre de priorite :

```text
1. Alpaca official current documentation
2. alpaca-py source for pinned version
3. real sanitized PAPER evidence
4. PyTradeKit canonical invariants
5. historical provider documentation only as secondary context
```

Le Domain PyTradeKit reste autoritaire sur les invariants canoniques.

Le provider reste autoritaire sur les faits Alpaca.

---

## 5. SDK freeze

Version :

```text
alpaca-py==0.44.0
```

Le pin reste exact pendant le milestone 0.5.

Aucun passage a :

```text
>=0.44
```

ou :

```text
latest
```

sans requalification.

---

## 6. Pourquoi le pin est exact

Le contrat depend de details observes dans cette version :

```text
OrderStatus members
TradeEvent members
TradingClient behavior
TradingStream behavior
RESTClient retry behavior
request/response models
```

Un upgrade peut ajouter :

```text
new states
new events
new retry behavior
new validation behavior
```

La CI doit detecter ces changements.

---

## 7. Surface provider retenue

Dans 0.5 :

```text
Trading API
Market Data API
```

sont dans le perimetre.

Hors scope :

```text
Broker API
OAuth/Connect
account opening
KYC
funding
multi-user brokerage
```

---

## 8. Environment freeze

Environment unique autorise :

```text
PAPER
```

Le runtime 0.5 ne propose pas :

```text
LIVE
```

comme valeur de configuration utilisable.

---

## 9. Fail closed

Toute configuration qui n'est pas explicitement PAPER doit echouer.

Jamais :

```text
environment missing
-> use LIVE
```

---

## 10. Credentials

Credentials attendus :

```text
PAPER API key
PAPER secret key
```

Ils sont distincts des credentials LIVE.

Ils doivent provenir de :

```text
SecretsPort
```

dans le runtime final.

Les probes peuvent utiliser des variables d'environnement de test.

---

## 11. Account identity

Le runtime final doit exiger une identite de compte attendue.

Readiness :

```text
credentials resolved
AND
PAPER endpoint
AND
account fetched
AND
returned account identity == expected account identity
```

Sinon :

```text
NOT READY
```

---

## 12. Scope instrument

Le vertical slice 0.5 qualifie :

```text
US_EQUITY
```

Les autres classes restent hors scope initial :

```text
US_OPTION
CRYPTO
CRYPTO_PERP
```

---

## 13. Scope ordre

Le contrat 0.5 supporte uniquement :

```text
MARKET
LIMIT
CANCEL
QUERY ORDER
```

---

## 14. Time in Force

Le contrat gele :

```text
DAY
```

comme TIF supporte pour le premier vertical slice.

Le fait qu'Alpaca supporte davantage de TIF ne les rend pas automatiquement supportes par PyTradeKit 0.5.

---

## 15. Explicitly out of scope order types

```text
STOP
STOP_LIMIT
TRAILING_STOP
```

---

## 16. Explicitly out of scope mutations

```text
replace order
cancel all
close all positions
close position
exercise options
```

---

## 17. ExecutionPort remains canonical

Le port existant reste la frontiere consumer-owned :

```text
submit(order)
cancel(order)
query_order(order)
```

Le contrat Alpaca doit s'y conformer.

Aucun `AlpacaExecutionPort` n'est ajoute au Domain.

---

## 18. SubmissionResult freeze

Le submit immediat peut produire :

```text
ACKNOWLEDGED
REJECTED
UNCERTAIN
```

Le provider adapter ne doit pas transformer un timeout en :

```text
REJECTED
```

sans preuve.

---

## 19. CancelResult freeze

Le cancel immediat peut produire :

```text
ACKNOWLEDGED
REJECTED
UNCERTAIN
```

Une erreur transport ne signifie pas automatiquement :

```text
cancel failed
```

---

## 20. ExecutionCertainty

Le concept canonique :

```text
CONFIRMED
UNCERTAIN
```

reste la representation Domain de la connaissance sur le resultat d'une operation economique.

Les details transport restent dans l'infrastructure.

---

## 21. ClientOrderReference

Le Domain actuel porte :

```text
Order.client_order_id
```

Le freeze confirme qu'il constitue la reference client provider-neutral necessaire a Alpaca.

Pour Alpaca :

```text
Order.client_order_id
-> Alpaca client_order_id
```

---

## 22. client_order_id before submit

Invariant :

```text
client_order_id exists
BEFORE
provider submission
```

Il doit etre durable avant tout effet distant dans le runtime final.

---

## 23. Alpaca limit

Longueur maximale retenue :

```text
128 characters
```

La validation provider-specific reste dans l'ACL.

Le Domain ne doit pas adopter cette limite Alpaca comme limite universelle.

---

## 24. Provider order identity

Mapping :

```text
canonical OrderId
        |
        +-- client_order_id
        |
        +-- Alpaca Order.id
```

`Alpaca Order.id` reste :

```text
external provider identity
```

et ne remplace jamais `OrderId`.

---

## 25. Provider fill identity

Mapping :

```text
canonical FillId
        |
        +-- Alpaca execution_id
```

`execution_id` devient la candidate prioritaire pour :

```text
external_fill_id
```

lorsqu'il est present.

---

## 26. Fill idempotency

Invariant local :

```text
same external_fill_id
=> one economic fill effect
```

La persistence et le ProcessedFillRegistry protegent cet invariant.

---

## 27. Command transport freeze

Les commandes economiques n'utilisent jamais le retry automatique du SDK.

Regle :

```text
one application command
=> at most one transport submit attempt
```

---

## 28. alpaca-py retry behavior

La version qualifiee utilise par defaut :

```text
3 retries
```

sur certains codes provider, dont notamment :

```text
429
504
```

dans le RESTClient generique.

Ce comportement est acceptable pour certains reads.

Il est interdit implicitement pour les commandes economiques.

---

## 29. Single-attempt command client

Le probe 45 demontre un mecanisme :

```text
SDK retry counter = 0
```

avec :

```text
one submit_order call site
one cancel_order_by_id call site
```

---

## 30. Production command transport decision

Pour LOT-05/Alpaca execution adapter :

```text
MUST preserve single-attempt economics
```

L'implementation peut :

```text
wrap pinned SDK internals
```

ou :

```text
introduce a dedicated safe HTTP command transport
```

mais elle ne peut pas reintroduire le retry economique implicite.

---

## 31. Read retry policy

Les operations idempotentes de lecture peuvent utiliser un retry borne.

Exemples :

```text
get_account
get_asset
get_orders
get_order_by_id
get_order_by_client_id
get_all_positions
get_clock
latest quote
```

---

## 32. Retry classification

```text
READ
-> bounded retry may be allowed

WRITE
-> one transport attempt

WRITE UNKNOWN OUTCOME
-> reconcile
```

---

## 33. UNCERTAIN recovery

Le primitive Alpaca principale est :

```text
get_order_by_client_id
```

Flow :

```text
submit once
    |
    X response unavailable
    |
    v
UNCERTAIN
    |
    v
query by client_order_id
```

---

## 34. No automatic resubmit

Si la query ne retrouve pas immediatement l'ordre :

```text
remain UNCERTAIN
```

puis lancer une reconciliation bornee.

Jamais :

```text
not found
=> submit again
```

---

## 35. Controlled probe evidence

Le probe 45 repete le scenario suivant :

```text
provider accepts
response deliberately discarded
state becomes UNCERTAIN
query by client_order_id
provider order recovered
resubmitted = false
```

Cela valide le workflow logique.

---

## 36. Limite de la preuve

Le probe ne prouve pas encore un vrai :

```text
TCP reset
HTTP 504 post-accept
process crash after send
```

Ces scenarios restent des tests de fault qualification futurs.

---

## 37. Status mapping principle

Le Domain ne copie pas tous les `OrderStatus` Alpaca.

Chaque status provider doit recevoir une disposition explicite :

```text
MAP
TRANSIENT
RECONCILE
OUT_OF_SCOPE
```

---

## 38. MAP

Un provider status `MAP` produit un fait canonique.

---

## 39. TRANSIENT

Un provider status `TRANSIENT` ne cree pas de nouvel etat Domain.

Il represente un detail provider deja couvert par :

```text
SUBMITTED
CANCEL_REQUESTED
```

ou par la progression locale.

---

## 40. RECONCILE

Un provider status `RECONCILE` n'est pas mappe automatiquement.

Il declenche :

```text
state refresh
diagnostic
provider reconciliation
```

plutot qu'une extension automatique du Domain.

---

## 41. OUT_OF_SCOPE

Un provider status `OUT_OF_SCOPE` correspond a une fonctionnalite non supportee par 0.5.

Exemple :

```text
replace
```

Il ne doit pas etre silencieusement traduit.

---

## 42. Frozen OrderStatus mapping

```text
accepted
-> ACCEPTED

pending_new
-> TRANSIENT

new
-> ACCEPTED

partially_filled
-> PARTIALLY_FILLED

filled
-> FILLED

pending_cancel
-> TRANSIENT

canceled
-> CANCELLED

expired
-> EXPIRED

rejected
-> REJECTED
```

---

## 43. OrderStatus reconciliation-only

```text
done_for_day
pending_review
accepted_for_bidding
stopped
suspended
calculated
held
```

Disposition :

```text
RECONCILE
```

---

## 44. OrderStatus out of scope

```text
pending_replace
replaced
```

Disposition :

```text
OUT_OF_SCOPE
```

---

## 45. TradeEvent mapping

```text
accepted
-> ACCEPTED

pending_new
-> TRANSIENT

new
-> ACCEPTED

partial_fill
-> PARTIALLY_FILLED

fill
-> FILLED

pending_cancel
-> TRANSIENT

canceled
-> CANCELLED

expired
-> EXPIRED

rejected
-> REJECTED
```

---

## 46. TradeEvent out of scope

```text
pending_replace
replaced
```

---

## 47. TradeEvent reconciliation-only

```text
restated
```

---

## 48. Exhaustiveness fitness function

Le code de freeze contient une regle pour :

```text
every AlpacaOrderStatus
every AlpacaTradeEvent
```

de `alpaca-py==0.44.0`.

Un nouveau member SDK doit casser la CI jusqu'a decision explicite.

---

## 49. Why this matters

Sans ce test, un SDK upgrade pourrait ajouter :

```text
provider state X
```

et l'adapter pourrait :

```text
ignore it accidentally
```

Le freeze transforme ce risque en :

```text
compile/test-time architecture decision
```

---

## 50. Fill mapping

Un `partial_fill` ou `fill` doit produire un Fill canonique avec :

```text
FillId internal
OrderId canonical
Quantity Decimal-backed
Price Decimal-backed
occurred_at UTC
external_fill_id = execution_id when available
```

---

## 51. No float truth

Les models SDK peuvent exposer :

```text
str
float
```

selon les surfaces.

L'ACL doit convertir vers :

```text
Decimal
Quantity
Price
Money
```

avant de creer les facts canoniques.

---

## 52. Time normalization

Tous les timestamps provider deviennent :

```text
timezone-aware UTC
```

avant d'entrer dans le Domain.

---

## 53. Stream role

`TradingStream` fournit :

```text
provider facts
```

Il ne constitue pas un command acknowledgement channel canonique.

---

## 54. Stream pipeline

Cible :

```text
TradingStream
    |
    v
raw TradeUpdate
    |
    v
Inbox
    |
    v
Alpaca mapper
    |
    v
ExecutionReport / Fill
    |
    v
Orders
    |
    v
Portfolio
    |
    v
Outbox
```

---

## 55. Stream reconnect

SDK reconnect :

```text
transport recovery
```

Il n'est pas :

```text
business state recovery
```

---

## 56. Reconnect policy

Apres une interruption significative :

```text
reconnect
    |
    v
query snapshots
    |
    v
reconcile unresolved orders
    |
    v
READY
```

---

## 57. Snapshot contract

Le runtime Alpaca doit pouvoir charger :

```text
account
positions
open orders
order by ID
order by client_order_id
asset metadata
market clock
```

---

## 58. Market data contract

Le vertical slice requiert au minimum :

```text
latest quote
```

pour US equity.

---

## 59. Market data feed baseline

Baseline de qualification :

```text
IEX
```

Un autre feed peut devenir une capability/configuration si le compte y a droit.

---

## 60. Feed entitlement

Le runtime ne doit pas supposer :

```text
SIP available
```

sans preuve de plan/entitlement.

---

## 61. Market data and execution separation

```text
Execution provider facts
!=
Market data feed facts
```

Le runtime peut a terme composer des providers differents.

---

## 62. Account snapshot

Les fields provider restent des observations.

Exemples :

```text
cash
equity
buying power
trading_blocked
account_blocked
```

Ils ne deviennent pas automatiquement tous des Domain primitives.

---

## 63. Position snapshot

Le provider position est projete vers le Portfolio canonique.

Le snapshot provider reste une source de reconciliation.

---

## 64. Order snapshot

Les ordres provider doivent etre correlables via :

```text
client_order_id
external_order_id
```

---

## 65. Persistence mapping

Le runtime dispose deja de :

```text
runtime.broker_mappings
```

pour relier identites canoniques et provider.

---

## 66. Mapping types recommandes

Pour Alpaca :

```text
order.client_reference
order.external_id
fill.external_id
account.external_id
instrument.external_id
```

Les noms exacts peuvent rester une convention d'application, mais leur semantique est gelee.

---

## 67. Provider key

Provider key :

```text
alpaca
```

La casse doit rester stable dans la persistence.

---

## 68. Mapping uniqueness

Une external identity doit etre unique dans son :

```text
provider
mapping_type
```

selon la contrainte durable existante.

---

## 69. Account mapping

Le compte canonique PyTradeKit conserve son propre `AccountId`.

Alpaca account ID reste external.

---

## 70. Instrument mapping

`InstrumentId` canonique ne devient jamais :

```text
AAPL
```

ni :

```text
Alpaca asset UUID
```

Le mapping provider relie les deux.

---

## 71. Capability contract

0.5 supporte :

```text
US_EQUITY
MARKET
LIMIT
DAY
CANCEL
ORDER_QUERY
ACCOUNT_QUERY
POSITION_QUERY
LATEST_QUOTE
TRADE_UPDATES
```

---

## 72. Unsupported does not mean Alpaca cannot do it

Cela signifie seulement :

```text
PyTradeKit 0.5 does not promise it
```

---

## 73. Error taxonomy

Le provider adapter doit distinguer au minimum :

```text
AuthenticationError
AuthorizationError
InvalidOrder
ProviderRejectedOrder
RateLimited
ProviderUnavailable
ProviderProtocolError
UnknownSubmissionOutcome
```

---

## 74. Error mapping principle

Une erreur HTTP/SDK n'est pas automatiquement un business rejection.

Le contexte operationnel est obligatoire.

---

## 75. Read-side 429/504

Pour un read idempotent :

```text
bounded retry
```

peut etre acceptable.

---

## 76. Write-side 429/504

Pour un submit apres tentative reseau :

```text
UNCERTAIN
```

reste la disposition conservative sauf preuve que le provider n'a pas accepte.

---

## 77. SDK exception is not Domain exception

Les exceptions :

```text
alpaca.common.exceptions.*
requests.*
websockets.*
```

ne doivent pas traverser le public API.

---

## 78. Mapper responsibility

L'ACL convertit :

```text
provider model
provider enum
provider exception
```

vers :

```text
canonical result
canonical fact
application/runtime error
```

---

## 79. Rejection reason

Un reject canonique doit conserver une reason exploitable.

Le provider code/message brut peut etre conserve en metadata infrastructure.

---

## 80. Inbox identity

Pour un Fill :

```text
execution_id
```

est la cle provider prioritaire.

Pour les events sans execution ID, une strategie stable doit etre definie par le mapper.

---

## 81. Do not invent event identity

Si un event ne possede pas d'ID provider stable :

```text
do not pretend exactly-once transport delivery
```

Utiliser :

```text
semantic deduplication
+
order state convergence
```

---

## 82. Outbox role

Les events canoniques produits apres traitement provider doivent etre enregistres atomiquement avec les mutations locales.

---

## 83. UnitOfWork role

Transaction cible :

```text
Inbox claim
+
Order update
+
Fill insert
+
Portfolio update
+
Outbox records
```

---

## 84. Local exactly-once economic effect

Objectif :

```text
at-least-once provider observation
+
idempotent Inbox/Fill processing
=
one local economic effect
```

---

## 85. No distributed ACID illusion

La transaction PostgreSQL ne peut pas englober :

```text
remote Alpaca side effect
```

D'ou :

```text
UNCERTAIN
reconciliation
```

---

## 86. Runtime profile requirements

LOT-05 doit rendre explicite :

```text
environment
account identity
credential references
market data feed
provider key
SDK/version manifest
```

---

## 87. Environment representation

Le runtime peut utiliser une abstraction provider-neutral, mais le composition root Alpaca doit toujours aboutir a :

```text
PAPER
```

en 0.5.

---

## 88. Readiness contract

Le runtime ne devient READY que si :

```text
environment == PAPER
credentials resolved
account identity matches
account not blocked
asset/instrument mappings loaded
provider session healthy
snapshots loaded
reconciliation completed
trade stream ready
```

Les details exacts de health implementation appartiennent LOT-05.

---

## 89. Startup sequence

Cible :

```text
01 load runtime profile
02 require PAPER
03 resolve secrets
04 initialize PostgreSQL
05 verify migrations
06 build read client
07 build single-attempt command transport
08 fetch account
09 verify account identity
10 load instrument mappings
11 load unresolved local orders
12 fetch provider orders/positions
13 reconcile
14 start trade_updates
15 expose READY
```

---

## 90. Shutdown sequence

Cible :

```text
stop new admissions
stop strategy submissions
stop stream
finish/abort local handlers safely
persist final metadata
close provider clients
close DB resources
```

Aucun cleanup economique automatique implicite.

---

## 91. Provider manifest

Le runtime doit pouvoir exposer un diagnostic similaire a :

```text
provider = alpaca
environment = PAPER
sdk = alpaca-py
sdk_version = 0.44.0
asset_scope = US_EQUITY
order_types = MARKET,LIMIT
tif = DAY
```

---

## 92. Observability

Minimum :

```text
alpaca_submit_total
alpaca_submit_uncertain_total
alpaca_cancel_total
alpaca_cancel_uncertain_total
alpaca_recovery_query_total
alpaca_trade_updates_total
alpaca_stream_reconnect_total
alpaca_reconciliation_unresolved_total
```

---

## 93. Structured log context

```text
provider
environment
operation
canonical_order_id
client_order_id
external_order_id
execution_id
correlation_id
provider_status
```

---

## 94. Secrets must never be logs

Interdit :

```text
API key
secret key
auth headers
```

---

## 95. Account identity logs

Preferer :

```text
masked account identity
internal account alias
```

---

## 96. PAPER semantic warning

PAPER n'est pas une simulation parfaite du LIVE.

La qualification PAPER prouve :

```text
API compatibility
basic order lifecycle
stream integration
reconciliation workflow
```

Elle ne prouve pas :

```text
live liquidity
latency
market impact
queue position
true slippage
production fees
```

---

## 97. Replace remains deferred

Le Domain possede deja `REPLACED`.

Cela ne signifie pas que le provider adapter 0.5 doit supporter :

```text
replace_order_by_id
```

Cette operation reste hors scope.

---

## 98. Rare provider states

Les states rares ne doivent pas entrainer :

```text
automatic domain growth
```

Leur traitement par defaut est :

```text
RECONCILE
```

jusqu'a preuve d'une semantique canonique necessaire.

---

## 99. Unknown future states

Grace aux contract tests :

```text
new Alpaca enum member
=> CI failure
```

Le developpeur doit alors choisir :

```text
MAP
TRANSIENT
RECONCILE
OUT_OF_SCOPE
```

---

## 100. Upgrade policy

Pour changer de version `alpaca-py` :

```text
01 update dependency in dedicated PR
02 run enum exhaustiveness tests
03 inspect SDK retry implementation
04 inspect TradingStream reconnect changes
05 run unit/architecture tests
06 run probe 44 against PAPER
07 run probe 45 against PAPER
08 compare sanitized evidence
09 update contract if needed
10 only then merge
```

---

## 101. Dependency isolation

`alpaca.*` reste interdit hors :

```text
pytradekit.brokers.adapters.alpaca
```

selon les architecture tests existants.

---

## 102. Public API rule

Aucun type :

```text
alpaca.trading.models.Order
TradeUpdate
TradingClient
TradingStream
```

ne doit apparaitre dans les ports publics PyTradeKit.

---

## 103. Production adapter package

Cible possible :

```text
pytradekit.brokers.adapters.alpaca
|
+-- contract.py
+-- config.py
+-- execution.py
+-- snapshots.py
+-- stream.py
+-- mappers.py
+-- errors.py
+-- reconciliation.py
```

La topologie exacte peut evoluer sans changer les invariants du freeze.

---

## 104. Contract code artifact

Le freeze introduit :

```text
src/pytradekit/brokers/adapters/alpaca/contract.py
```

Il contient :

```text
provider key
environment
SDK target
client order ID provider limit
supported order types
supported TIF
OrderStatus rules
TradeEvent rules
```

---

## 105. Contract tests

Tests :

```text
all SDK OrderStatus members classified
all SDK TradeEvent members classified
direct mappings stable
pending states transient
replace states out of scope
rare states reconciliation-only
MARKET/LIMIT DAY scope stable
client_order_id limit stable
```

---

## 106. Architecture freeze tests

Ils verifient :

```text
alpaca-py exact pin
PAPER-only contract
single submit call site in controlled probe
single cancel call site in controlled probe
SDK command retry counter forced to zero
no unsupported provider mutation in frozen contract
```

---

## 107. What is not frozen as a Domain concept

Ne sont pas promus dans le Domain par ce lot :

```text
AlpacaStateDisposition
Alpaca feed enum
Alpaca SDK retry fields
TradingStream reconnect details
provider HTTP status codes
provider request IDs
```

Ils restent infrastructure/provider-specific.

---

## 108. What is not implemented yet

Le freeze ne remplace pas :

```text
production AlpacaExecutionAdapter
production TradeUpdate consumer
runtime profile
SecretsPort
startup orchestrator
reconciliation service
provider health model
```

Ils appartiennent aux lots suivants.

---

## 109. Real PAPER evidence still missing

Aucun secret utilisateur n'est present dans la branche.

Par consequent, dans cet environnement :

```text
probe 44 real provider run
probe 45 real provider run
```

n'ont pas ete executes.

---

## 110. Release-blocking evidence

Avant `v0.5.0`, il faudra archiver des preuves sanitisees montrant :

```text
PAPER auth success
expected account match
read snapshots success
latest quote success
trade stream success
MARKET submit success
client_order_id recovery success
LIMIT submit success
CANCEL success
cleanup success
no blind retry
```

---

## 111. Provider qualification result

Aujourd'hui :

```text
DESIGN QUALIFIED      YES
CODE CONTRACT         YES
CI CONTRACT           YES
REAL PAPER EVIDENCE   PENDING
LIVE QUALIFICATION    OUT OF SCOPE
```

---

## 112. LOT-05 entry gate

LOT-05 peut commencer parce que :

```text
provider boundary is frozen
command safety policy is frozen
identity strategy is frozen
mapping strategy is frozen
reconciliation strategy is frozen
scope is frozen
```

---

## 113. LOT-05 must not reopen discovery

LOT-05 ne doit pas reposer la question :

```text
should we use Broker API?
should LIVE be enabled?
should we support STOP?
should we blindly retry submit?
should Alpaca IDs become canonical?
```

Ces decisions sont closes pour 0.5.

---

## 114. Legitimate LOT-05 decisions

LOT-05 peut encore decider :

```text
runtime profile data structure
SecretsPort interface
health model implementation
composition root
startup/shutdown orchestration
metrics integration
configuration file format
```

tant que les invariants de ce freeze sont respectes.

---

## 115. Change control

Tout changement des points suivants exige une mise a jour de ce document et des contract tests :

```text
SDK version
environment
asset scope
order types
TIF
client order ID policy
single-attempt command policy
status/event mapping
reconciliation semantics
provider identity semantics
```

---

## 116. Security gate

Le runtime final doit prouver :

```text
no LIVE fallback
no raw secret logs
expected account verification
single-attempt command path
no blind retry after uncertainty
```

---

## 117. Data integrity gate

Il doit aussi prouver :

```text
Decimal conversion
UTC timestamps
external fill deduplication
canonical/provider identity separation
atomic local event processing
```

---

## 118. Restart gate

Avant release :

```text
unresolved order persisted
runtime restarted
provider queried
order converged
no duplicate submit
```

doit etre teste.

---

## 119. Stream gap gate

Avant release :

```text
stream interrupted
stream reconnects
snapshot/reconciliation runs
READY only after convergence
```

doit etre teste.

---

## 120. Contract freeze statement

Le contrat Alpaca PyTradeKit 0.5 est donc :

```text
PAPER-only
US-equity-only
MARKET/LIMIT/DAY
single-attempt writes
read retries allowed when bounded
client_order_id persisted before submit
UNCERTAIN on unknown write outcome
recovery by client_order_id
provider IDs remain external
trade_updates are external facts
stream reconnect requires reconciliation
rare provider states do not expand Domain automatically
alpaca-py pinned to 0.44.0
```

---

## 121. Final gate

```text
LOT-04 DISCOVERY
CLOSED FOR ALPACA 0.5

LOT-05
OPEN FOR IMPLEMENTATION
```

avec :

```text
REAL PAPER PROBE EVIDENCE
RELEASE BLOCKER
```

---

## 122. Prochaine etape

La prochaine etape logique est :

```text
LOT-05 - PAPER Runtime Configuration
```

qui doit maintenant construire :

```text
RuntimeProfile
SecretsPort
PAPER environment guard
Alpaca provider manifest
composition root
startup readiness
shutdown behavior
```

sans modifier les invariants geles ici.

---

## 123. Decision summary

```text
Environment            PAPER only
SDK                    alpaca-py==0.44.0
Asset class            US_EQUITY
Order types            MARKET, LIMIT
TIF                    DAY
Cancel                 supported
Replace                out of scope
Command retry          zero implicit retries
Read retry             bounded allowed
Client reference       required before submit
Recovery key           client_order_id
External order ID      Alpaca Order.id
External fill ID       execution_id
Private facts          trade_updates
Market data baseline   IEX latest quote
Reconnect              transport only, then reconcile
LIVE                   out of scope
```

---

## 124. Final principle

> PyTradeKit controls the economic intent and canonical state. Alpaca supplies provider facts. Unknown remote outcomes are reconciled, never guessed.