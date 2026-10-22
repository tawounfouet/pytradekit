# 48 - PyTradeKit - LOT-06 Alpaca Anti-Corruption Layer

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-06 - Alpaca Anti-Corruption Layer`  
**Date :** 2026-10-22  
**Statut :** Implementation  
**Contrat provider :** `46_PYTRADEKIT_ALPACA_INTEGRATION_CONTRACT_FREEZE.md`  
**Runtime :** `47_PYTRADEKIT_LOT_05_PAPER_RUNTIME_CONFIGURATION.md`

---

## 1. Objectif

LOT-06 materialise la frontiere obligatoire entre le langage Alpaca et le langage PyTradeKit.

Principe :

```text
alpaca-py models / enums / errors
              |
              v
      Alpaca ACL
              |
     +--------+--------+
     |        |        |
     v        v        v
 identities mappers  errors
     |        |        |
     +--------+--------+
              |
              v
 provider-neutral PyTradeKit contracts
```

Aucun type `alpaca.*` ne doit atteindre le Domain, l'Application ou la Persistence publique.

---

## 2. Scope implemente

```text
Provider-neutral identity models
Provider-neutral account/instrument/position/order snapshots
Alpaca identity translation
Asset mapper
Account mapper
Position mapper
Order state mapper
Order query -> ExecutionReport mapper
TradeUpdate -> ExecutionReport/Fill mapper
Submission ACK mapper
Alpaca error translation
ADR-004 Broker Anti-Corruption Layer
Architecture fitness functions
```

---

## 3. Provider-neutral identity models

Nouveaux contrats :

```text
ProviderOrderIdentity
ProviderFillIdentity
ProviderAccountIdentity
ProviderInstrumentIdentity
```

Ils conservent les identites provider sans les promouvoir en IDs canoniques.

Exemple :

```text
OrderId
  !=
Alpaca Order.id
```

et :

```text
InstrumentId
  !=
Alpaca Asset.id
```

---

## 4. ProviderExecutionContext

Un mapper d'execution ne cree jamais l'identite canonique a partir du provider.

Il recoit :

```text
OrderId
CorrelationId
ClientOrderReference
quote Currency
```

puis valide que l'objet Alpaca correspond bien au contexte attendu.

---

## 5. ProviderAccountSnapshot

L'account mapper produit :

```text
canonical Account
canonical cash Balance optional
provider Account identity
equity
buying power
portfolio value
trading_blocked
account_blocked
observed_at UTC
```

`buying_power` n'est PAS mappe vers `Balance.available`.

Raison :

```text
buying power
!=
cash available
```

notamment sur un compte margin.

---

## 6. ProviderPositionSnapshot

Un snapshot Alpaca position contient :

```text
canonical AccountId
canonical InstrumentId
provider instrument identity
signed quantity
average price
market value
cost basis
unrealized PnL
current price
available quantity
observed_at
```

Le mapper ne fabrique pas de :

```text
realized PnL
```

car le snapshot Alpaca de position ouverte ne fournit pas cette verite complete.

---

## 7. Long / Short mapping

Alpaca fournit :

```text
qty
side = long | short
```

Le snapshot PyTradeKit traduit en :

```text
LONG  -> +quantity
SHORT -> -quantity
```

Cela produit une quantite signee canonique sans importer `Alpaca PositionSide` hors de l'ACL.

---

## 8. Instrument mapping

Pour `US_EQUITY` :

```text
Alpaca Asset.id
    -> ProviderInstrumentIdentity.external_id

Alpaca symbol
    -> external_symbol

PyTradeKit InstrumentId
    -> supplied by canonical reference context
```

Le mapper ne fait jamais :

```text
InstrumentId = Alpaca asset UUID
```

---

## 9. ContractSpecification mapping

Alpaca metadata :

```text
price_increment
min_trade_increment
min_order_size
```

sont traduits vers :

```text
tick_size
quantity_step
min_quantity
```

avec `Decimal` uniquement.

---

## 10. No float truth

Les valeurs provider peuvent etre exposees comme :

```text
str
float
```

L'ACL normalise toujours via :

```text
Decimal(str(value))
```

puis construit :

```text
Money
Price
Quantity
Decimal
```

Aucun `float(...)` n'est autorise dans les mappers economiques.

---

## 11. Order identity

Mapping :

```text
Order.client_order_id
    -> ProviderOrderIdentity.client_reference

Order.id
    -> ProviderOrderIdentity.external_order_id
```

Le `client_order_id` recu doit correspondre au `ProviderExecutionContext` attendu.

Un mismatch est un :

```text
ProviderProtocolError
```

et non un nouvel ordre canonique.

---

## 12. Fill identity

Pour un `trade_update` contenant une execution :

```text
execution_id
    -> external_fill_id
```

Le `FillId` canonique reste distinct.

LOT-06 utilise un UUID v5 stable derive de :

```text
pytradekit:alpaca:fill:<execution_id>
```

Cela garantit :

```text
same Alpaca execution
-> same canonical FillId
```

sans reutiliser directement l'UUID provider comme identite canonique.

---

## 13. TradeUpdate mapper

Pipeline :

```text
TradeUpdate
    |
    v
validate client_order_id
    |
    v
classify TradeEvent
    |
    +-- TRANSIENT -> None
    |
    +-- OUT_OF_SCOPE -> ProviderUnsupportedStateError
    |
    +-- RECONCILE -> ProviderStateReconciliationRequired
    |
    +-- MAP
            |
            v
       ExecutionReport
            |
            +-- Fill if partial_fill/fill
```

---

## 14. Fill mapping

Un Fill exige :

```text
execution_id
qty
price
timestamp
```

Si une information critique manque :

```text
ProviderProtocolError
```

Aucune valeur economique n'est inventee.

---

## 15. Order query mapper

Un query Alpaca `Order` peut etre mappe directement pour :

```text
ACCEPTED
CANCELLED
EXPIRED
REJECTED
```

Les etats transitoires retournent :

```text
None
```

Les etats rares utilisent :

```text
ProviderStateReconciliationRequired
```

---

## 16. Filled order snapshot rule

Point critique :

```text
Alpaca Order
```

contient :

```text
filled_qty
filled_avg_price
```

mais ne fournit pas l'identite individuelle de chaque execution.

Donc :

```text
FILLED order snapshot
!=
canonical Fill
```

LOT-06 interdit de fabriquer un Fill a partir de la quantite cumulative et du prix moyen.

Il leve :

```text
ProviderStateReconciliationRequired
```

pour recuperer les executions reelles.

---

## 17. Pourquoi cette decision est importante

Sinon :

```text
partial fill A
partial fill B
```

pourraient etre remplaces artificiellement par :

```text
one fake average Fill
```

ce qui detruirait :

```text
execution identity
fees
exact prices
idempotency
auditability
```

---

## 18. Order state snapshot

Pour la reconciliation, l'ACL expose aussi :

```text
ProviderOrderStateSnapshot
```

avec :

```text
canonical OrderId
provider identities
provider status
canonical status if known
filled quantity cumulative
filled average price
observed_at
```

Ce snapshot est une observation, pas un Fill.

---

## 19. Submission ACK

La reponse Alpaca au submit est traduite en :

```text
SubmissionResult.ACKNOWLEDGED
```

avec :

```text
external_order_id = Alpaca Order.id
```

si le `client_order_id` correspond a la commande envoyee.

---

## 20. Provider error hierarchy

Nouveaux errors provider-neutral :

```text
ProviderError
ProviderAuthenticationError
ProviderAuthorizationError
ProviderRateLimitError
ProviderUnavailableError
ProviderRejectedOperationError
ProviderProtocolError
ProviderUncertainOutcomeError
ProviderStateReconciliationRequired
ProviderUnsupportedStateError
```

Aucun `alpaca.common.exceptions.APIError` ne doit sortir de l'adapter.

---

## 21. Error classification

### 401

```text
ProviderAuthenticationError
```

### 403

```text
ProviderAuthorizationError
```

### 429 read

```text
ProviderRateLimitError
```

### 429 write

```text
ProviderUncertainOutcomeError
```

Le choix est volontairement conservateur car la commande economique ne doit pas etre resoumise aveuglement.

---

## 22. 5xx classification

Read :

```text
ProviderUnavailableError
```

Economic write :

```text
ProviderUncertainOutcomeError
```

---

## 23. Known 4xx economic rejection

Pour une operation write connue :

```text
ProviderRejectedOperationError
```

La reason provider est conservee dans un message sanitise et le provider code reste disponible comme metadata d'erreur.

---

## 24. Unknown transport exception

Read :

```text
ProviderUnavailableError
```

Submit / Cancel :

```text
ProviderUncertainOutcomeError
```

Cette regle preserve :

```text
NO BLIND RETRY
```

---

## 25. Architecture boundaries

Les models generiques :

```text
pytradekit.brokers.models
pytradekit.brokers.errors
```

n'importent aucun SDK provider.

Le SDK Alpaca reste confine a :

```text
pytradekit.brokers.adapters.alpaca
```

---

## 26. Fitness functions

LOT-06 ajoute les gates suivantes :

```text
Alpaca SDK confined to adapter
provider-neutral broker models import no Alpaca
provider IDs never become canonical IDs
no float() in economic mapper
filled order query cannot fabricate Fill
```

---

## 27. ADR

LOT-06 materialise :

```text
docs/adr/ADR-004_BROKER_ANTI_CORRUPTION_LAYER.md
```

Decision :

> Every provider integration must translate provider language into PyTradeKit language before crossing the broker boundary.

---

## 28. Ce que LOT-06 ne fait pas encore

```text
no real ExecutionPort adapter
no submit network call
no cancel network call
no query orchestration
no TradingStream consumer loop
no snapshot persistence adapter
no startup reconciliation
```

Ces responsibilities restent aux lots suivants.

---

## 29. Output structure

```text
pytradekit/brokers/
|
+-- errors.py
+-- models.py
|
+-- adapters/alpaca/
    +-- errors.py
    +-- identities.py
    +-- mappers.py
```

---

## 30. Next lot

Le prochain lot logique est :

```text
LOT-07 - Alpaca Execution
```

Il pourra maintenant implementer `ExecutionPort` sans aucune logique de transformation ad hoc :

```text
submit
cancel
query_order
```

s'appuieront sur :

```text
RuntimeProfile / command client      LOT-05
Alpaca contract                      46
ACL identities/errors/mappers        LOT-06
```

---

## 31. Final principle

> Provider data may enter PyTradeKit only after its identity, numeric semantics, lifecycle meaning, and failure semantics have been translated explicitly.
