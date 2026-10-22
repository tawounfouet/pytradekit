# 49 - PyTradeKit - LOT-07 Alpaca Execution

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-07 - Alpaca Execution`  
**Date :** 2026-10-22  
**Statut :** Implementation  
**Precedents :** LOT-05 Runtime Configuration, LOT-06 Alpaca Anti-Corruption Layer

---

## 1. Objectif

LOT-07 implemente enfin le port canonique :

```text
ExecutionPort
```

contre Alpaca PAPER.

La frontiere devient :

```text
Orders Application
       |
       v
ExecutionPort
       |
       v
AlpacaExecutionAdapter
       |
       v
Alpaca ACL
       |
       v
alpaca-py
```

L'application Orders ne connait aucun type Alpaca.

---

## 2. Scope

LOT-07 implemente :

```text
submit MARKET
submit LIMIT
cancel
query_order
client_order_id recovery
safe error translation
single-attempt writes
```

Il ne couvre pas encore :

```text
production trade_updates consumer
fill stream processing
startup reconciliation orchestration
position/account snapshots runtime wiring
full trading readiness
```

---

## 3. ExecutionPort

Le port existant reste inchange :

```python
class ExecutionPort(Protocol):
    def submit(self, order: Order) -> SubmissionResult: ...
    def cancel(self, order: Order) -> CancelResult: ...
    def query_order(self, order: Order) -> ExecutionReport | None: ...
```

Aucun type provider n'est ajoute au contrat.

---

## 4. Injection des dependances

`AlpacaExecutionAdapter` recoit :

```text
AlpacaCommandClient
AlpacaReadClient
AlpacaInstrumentResolver
```

Il ne construit pas :

```text
TradingClient
SecretsPort
RuntimeProfile
```

Ces responsabilites restent dans LOT-05.

---

## 5. Instrument resolution

Le Domain fournit :

```text
InstrumentId
```

L'adapter exige un resolver vers :

```text
InstrumentMapping
```

puis verifie :

```text
mapping.instrument_id == order.instrument_id
mapping.provider == alpaca
external_symbol present
```

Le symbol Alpaca ne remplace jamais l'identite canonique.

---

## 6. MARKET mapping

```text
Order
  order_type = MARKET
  side
  quantity
  DAY
  client_order_id
        |
        v
MarketOrderRequest
```

---

## 7. LIMIT mapping

```text
Order
  order_type = LIMIT
  side
  quantity
  limit_price
  DAY
  client_order_id
        |
        v
LimitOrderRequest
```

---

## 8. Provider numeric boundary

Le Domain conserve :

```text
Decimal
```

`alpaca-py==0.44.0` declare encore certains request fields en :

```text
float
```

LOT-07 effectue donc une conversion uniquement au transport boundary.

La conversion est refusee si :

```text
Decimal(str(float(value))) != value
```

Cela interdit une perte silencieuse de precision.

---

## 9. Submit safety

Flow :

```text
canonical Order
      |
      v
validate frozen Alpaca contract
      |
      v
resolve InstrumentMapping
      |
      v
build provider request
      |
      v
ONE submit_order call
      |
      +-------------------+
      |                   |
      v                   v
known response        provider/transport error
      |                   |
      v                   +-- known 4xx -> REJECTED
ACKNOWLEDGED              |
                          +-- unknown write outcome -> UNCERTAIN
```

---

## 10. No blind retry

`AlpacaExecutionAdapter` ne contient :

```text
aucune boucle de retry
aucun second submit
aucun second cancel
```

Le client write-side fourni par LOT-05 est deja configure :

```text
_retry = 0
```

---

## 11. Known rejection

Un rejet provider connu devient :

```text
SubmissionResult(
    REJECTED
)
```

Il ne fuit pas une exception `alpaca.*` vers l'application.

---

## 12. Unknown submit

Un :

```text
504
5xx
transport exception
unknown API outcome
```

sur submit devient :

```text
SubmissionStatus.UNCERTAIN
```

L'application Orders applique alors :

```text
Order.mark_submission_uncertain()
```

---

## 13. Cancel

Si l'Order connait deja :

```text
external_order_id
```

LOT-07 effectue :

```text
ONE cancel_order_by_id
```

---

## 14. Cancel without external ID

Si l'ordre est UNCERTAIN et ne connait pas encore son provider ID :

```text
client_order_id
      |
      v
get_order_by_client_id
      |
      v
provider Order.id
      |
      v
ONE cancel_order_by_id
```

Aucun nouveau submit n'est effectue.

---

## 15. Cancel identity not found

Si l'ordre ne peut pas etre resolu par client reference :

```text
CancelStatus.UNCERTAIN
```

et non :

```text
REJECTED
```

car l'absence immediate d'une query n'est pas une preuve suffisante de non-existence economique.

---

## 16. Unknown cancel

Une erreur transport apres tentative de cancellation devient :

```text
CancelStatus.UNCERTAIN
```

Le lifecycle canonique conserve :

```text
CANCEL_REQUESTED
+
ExecutionCertainty.UNCERTAIN
```

jusqu'a reconciliation.

---

## 17. Query strategy

`query_order()` choisit :

```text
external_order_id available
-> get_order_by_id

otherwise
-> get_order_by_client_id
```

---

## 18. 404 semantics

Un 404 de query produit :

```text
None
```

Il ne provoque jamais :

```text
automatic resubmit
```

L'appelant peut continuer la reconciliation bornee.

---

## 19. Query mapping

Un provider snapshot complet et sans fill peut devenir :

```text
ExecutionReport
```

Exemples :

```text
NEW
ACCEPTED
CANCELED
EXPIRED
REJECTED
```

---

## 20. Filled snapshot rule

Si Alpaca renvoie uniquement :

```text
status = FILLED
filled_qty
filled_avg_price
```

LOT-07 refuse de fabriquer un Fill.

Il leve :

```text
ProviderStateReconciliationRequired
```

car les executions individuelles doivent etre recuperees.

---

## 21. Why no synthetic Fill

Un fill synthetique perdrait :

```text
execution_id
partial fills
individual execution prices
economic ordering
idempotency identity
audit trail
```

---

## 22. Error semantics

Le LOT-06 avait defini :

```text
ProviderRejectedOperationError
ProviderUncertainOutcomeError
ProviderAuthenticationError
ProviderAuthorizationError
ProviderUnavailableError
ProviderProtocolError
```

LOT-07 consomme cette taxonomie.

---

## 23. Error to ExecutionPort result

Pour les economic writes :

```text
ProviderRejectedOperationError
-> REJECTED

ProviderUncertainOutcomeError
-> UNCERTAIN
```

Les erreurs infrastructure/configuration non assimilables a un resultat economique restent des exceptions provider-neutral.

---

## 24. Architecture fitness functions

La CI verifie :

```text
one submit_order call site
one cancel_order_by_id call site
no client construction
no secret resolution
no LIVE endpoint
no retry loop
query_order cannot submit or cancel
```

---

## 25. Test matrix

Tests unitaires :

```text
ExecutionPort structural compatibility
MARKET mapping
LIMIT mapping
DAY contract
GTC local rejection
422 known rejection
504 uncertain submit
known external ID cancel
client_order_id cancel recovery
uncertain cancel
query by external ID
query by client reference
404 returns None
FILLED snapshot requires reconciliation
precision loss rejected before network
```

---

## 26. Ownership of order lifecycle

LOT-07 ne mute jamais directement :

```text
Order.status
Order.execution_certainty
Order.external_order_id
```

Cette responsabilite reste dans :

```text
SubmitOrder
CancelOrder
HandleExecutionReport
```

L'adapter retourne uniquement :

```text
SubmissionResult
CancelResult
ExecutionReport
```

---

## 27. Separation of concerns

```text
Application
owns lifecycle

Domain
owns invariants

AlpacaExecutionAdapter
owns command translation

Alpaca ACL
owns provider translation

alpaca-py
owns transport/SDK details
```

---

## 28. Runtime composition

LOT-05 construit deja :

```text
read_client
command_client
```

LOT-07 ajoute la derniere piece :

```text
AlpacaInstrumentResolver
```

necessaire pour obtenir le provider symbol.

L'adapter peut alors etre injecte dans :

```text
SubmitOrder
CancelOrder
```

via `ExecutionPort`.

---

## 29. Real PAPER gate

Comme les lots precedents :

```text
code qualified
CI qualified
```

ne remplace pas :

```text
real PAPER evidence
```

Avant `v0.5.0`, MARKET/LIMIT/CANCEL/recovery devront etre observes sur le compte PAPER attendu.

---

## 30. Next lot

LOT-08 pourra maintenant brancher :

```text
Alpaca Market Data
+
Account/Position snapshots
```

et utiliser les snapshots provider-neutral deja crees par LOT-06.

La suite execution evenementielle viendra ensuite avec :

```text
trade_updates
Inbox
Fill
OMS
Portfolio
reconciliation
```

---

## 31. Final invariant

> ExecutionPort speaks PyTradeKit. AlpacaExecutionAdapter speaks Alpaca. The anti-corruption layer is the only translator between them.
