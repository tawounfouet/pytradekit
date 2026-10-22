# 50 - PyTradeKit - LOT-08 Alpaca Market Data & Snapshots

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-08 - Alpaca Market Data & Snapshots`  
**Date :** 2026-10-22  
**Statut :** Implementation  
**Precedents :** LOT-05 Runtime Configuration, LOT-06 Alpaca ACL, LOT-07 Alpaca Execution

---

## 1. Objectif

LOT-08 construit le read-side Alpaca necessaire au runtime PAPER.

Il branche :

```text
asset/reference data
latest IEX quotes
account snapshots
position snapshots
```

sans modifier :

```text
ExecutionPort
submit flow
cancel flow
order lifecycle
```

---

## 2. Architecture

```text
                    PyTradeKit Runtime
                           |
              +------------+------------+
              |                         |
              v                         v
      AlpacaExecutionAdapter     AlpacaMarketDataSnapshots
              |                         |
              |                +--------+--------+
              |                |        |        |
              |                v        v        v
              |              Asset    Account  Positions
              |                         |
              |                         v
              |                    Latest Quote
              |                      IEX only
              |                         |
              +------------+------------+
                           |
                           v
                      Alpaca ACL
                           |
                           v
                       alpaca-py
```

LOT-07 gere les commandes economiques.

LOT-08 ne fait que lire et traduire des faits provider.

---

## 3. New canonical Quote

Le bounded context Market Data introduit :

```text
Quote
```

avec :

```text
instrument_id
bid_price
bid_size
ask_price
ask_size
occurred_at
```

La Quote ne connait :

```text
ni Alpaca
ni IEX
ni provider symbol
```

---

## 4. One-sided quotes

Les marches peuvent produire une quote sans bid ou sans ask exploitable.

Le modele autorise donc :

```text
bid_price = None
```

ou :

```text
ask_price = None
```

mais refuse :

```text
bid_price = None
AND
ask_price = None
```

---

## 5. Zero provider price

Si Alpaca retourne :

```text
bid_price = 0
```

LOT-08 ne tente pas de creer :

```text
Price(0)
```

car `Price` est strictement positif.

La semantique devient :

```text
0 provider side price
-> no priced side
-> None
```

La taille reste preservee en `Quantity`.

---

## 6. ProviderQuoteSnapshot

Le LOT ajoute l'enveloppe provider-neutral :

```text
ProviderQuoteSnapshot
```

qui contient :

```text
provider
InstrumentMapping
canonical Quote
feed
bid exchange
ask exchange
observed_at
```

---

## 7. Two clocks

Deux timestamps sont conserves :

```text
Quote.occurred_at
    = timestamp du feed Alpaca

ProviderQuoteSnapshot.observed_at
    = heure locale du read
```

Cela permettra plus tard de calculer :

```text
freshness
transport delay
observation latency
```

---

## 8. Market-data feed

Le contrat 0.5 reste :

```text
IEX
```

LOT-08 construit explicitement :

```text
StockLatestQuoteRequest(
    feed=DataFeed.IEX
)
```

Aucun fallback vers :

```text
SIP
OTC
DELAYED_SIP
```

n'est autorise.

---

## 9. Read-only service

Facade principale :

```text
AlpacaMarketDataSnapshots
```

Operations :

```text
get_asset_snapshot()
get_latest_quote()
get_account_snapshot()
get_position_snapshots()
```

---

## 10. Injected dependencies

Le service recoit :

```text
AlpacaSnapshotTradingClient
AlpacaStockDataClient
AlpacaSnapshotReferenceResolver
AccountId
expected provider account ID
ClockPort
```

Il ne construit aucun client.

---

## 11. Asset/reference flow

```text
InstrumentId
    |
    v
InstrumentMapping
    |
    v
external_id or symbol
    |
    v
TradingClient.get_asset()
    |
    v
Alpaca Asset
    |
    v
map_asset_snapshot()
    |
    v
ProviderInstrumentSnapshot
```

---

## 12. Asset snapshot output

Le snapshot LOT-06 est reutilise :

```text
ProviderInstrumentSnapshot
```

Il contient :

```text
canonical Instrument
InstrumentMapping
ProviderInstrumentIdentity
ContractSpecification
exchange
status
tradable
marginable
shortable
easy_to_borrow
fractionable
observed_at
```

---

## 13. Mapping verification

Si un mapping configure :

```text
external_symbol = AAPL
external_id = X
```

mais Alpaca repond :

```text
symbol != AAPL
```

ou :

```text
id != X
```

LOT-08 leve :

```text
ProviderProtocolError
```

Le runtime ne remappe jamais silencieusement une identite.

---

## 14. Reference resolver

LOT-08 introduit :

```text
StaticAlpacaReferenceResolver
```

Il fournit :

```text
InstrumentId -> InstrumentMapping
```

et :

```text
Alpaca external ID/symbol -> InstrumentMapping
```

---

## 15. Why bidirectional resolution

L'execution part du Domain :

```text
InstrumentId
-> provider symbol
```

Les positions provider arrivent dans l'autre sens :

```text
provider asset ID/symbol
-> InstrumentId
```

Les deux directions doivent converger sur le meme mapping canonique.

---

## 16. Resolver safety

Le resolver refuse :

```text
empty mapping set
non-Alpaca mapping
duplicate InstrumentId
duplicate provider symbol
duplicate external asset ID
```

---

## 17. Latest quote flow

```text
InstrumentId
    |
    v
InstrumentMapping
    |
    v
AAPL
    |
    v
StockLatestQuoteRequest
feed = IEX
    |
    v
get_stock_latest_quote()
    |
    v
Alpaca Quote
    |
    v
map_latest_quote()
    |
    v
ProviderQuoteSnapshot
```

---

## 18. Decimal normalization

Alpaca quote fields sont declares en `float`.

LOT-08 ne laisse jamais ces floats traverser la frontiere.

```text
provider float
    |
    v
str(value)
    |
    v
Decimal
    |
    v
Price / Quantity
```

Le Domain reste Decimal-backed.

---

## 19. Account snapshot flow

```text
get_account()
    |
    v
TradeAccount
    |
    +-- verify expected provider account ID
    |
    v
map_account_snapshot()
    |
    v
ProviderAccountSnapshot
```

---

## 20. Account identity safety

LOT-05 avait deja un expected provider account ID.

LOT-08 le reverifie lors du snapshot.

Le read-side ne doit jamais accepter silencieusement :

```text
different Alpaca account
```

---

## 21. Cash vs buying power

Le mapper LOT-06 est reutilise.

Il conserve :

```text
cash
!=
buying_power
!=
equity
!=
portfolio_value
```

Aucune fusion semantique n'est autorisee.

---

## 22. Position snapshot flow

```text
get_all_positions()
      |
      v
list[Alpaca Position]
      |
      v
provider asset ID/symbol
      |
      v
reverse InstrumentMapping
      |
      v
map_position_snapshot()
      |
      v
ProviderPositionSnapshot
```

---

## 23. Signed quantity

LOT-06 reste autoritaire :

```text
LONG  -> positive quantity
SHORT -> negative quantity
```

---

## 24. Missing position mapping

Une position distante inconnue est importante economiquement.

LOT-08 ne la saute jamais.

```text
provider position
+
no canonical mapping
        |
        v
ProviderStateReconciliationRequired
```

---

## 25. Why fail instead of skip

Ignorer une position pourrait produire :

```text
wrong portfolio exposure
wrong buying power assumptions
wrong risk
wrong reconciliation
```

Une position non mappee bloque donc la convergence.

---

## 26. Position snapshot semantics

Le snapshot preserve :

```text
average price
market value
cost basis
unrealized PnL
current price
available quantity
```

mais ne fabrique jamais :

```text
realized PnL
```

absent du provider snapshot.

---

## 27. Read error translation

Toutes les erreurs Alpaca read-side passent par :

```text
translate_alpaca_error(
    operation=READ
)
```

Donc :

```text
401 -> ProviderAuthenticationError
403 -> ProviderAuthorizationError
429 -> ProviderRateLimitError
5xx -> ProviderUnavailableError
```

Aucun type exception Alpaca ne doit sortir vers l'application.

---

## 28. No economic side effect

Le module LOT-08 n'a aucun appel :

```text
submit_order
cancel_order
replace_order
close_position
close_all_positions
exercise
POST
PATCH
DELETE
```

---

## 29. No ExecutionPort dependency

LOT-08 ne depend pas de :

```text
ExecutionPort
```

La lecture de marche et portfolio provider est separee du command path.

---

## 30. Runtime composition relationship

LOT-05 fournit deja :

```text
read_client
market_data_client
```

LOT-08 reutilise directement ces clients.

Il lui faut seulement :

```text
canonical AccountId
reference mappings
ClockPort
```

---

## 31. Separation from LOT-07

```text
LOT-07
economic commands
submit/cancel/query order

LOT-08
provider reads
asset/quote/account/positions
```

`query_order` reste dans LOT-07 car il appartient au lifecycle d'execution.

---

## 32. Architecture fitness functions

La CI verifie :

```text
snapshot layer is read-only
IEX is explicit
no SIP fallback
no client construction
no SecretsPort access
no ExecutionPort dependency
canonical Quote has no Alpaca dependency
reference resolver has no network calls
```

---

## 33. Unit qualification

Tests couvrent :

```text
canonical quote
one-sided quote
asset snapshot
canonical identity preservation
IEX latest quote
provider timestamp vs observation timestamp
zero price side
account identity verification
cash snapshot
position reverse mapping
signed quantity
unmapped provider position reconciliation
static resolver validation
```

---

## 34. What LOT-08 does not do

LOT-08 ne persiste pas encore automatiquement les snapshots.

Il ne fait pas encore :

```text
portfolio reconciliation write
asset catalog persistence
market quote cache
streaming market data
trade_updates
```

Ces operations appartiennent aux lots runtime/reconciliation suivants.

---

## 35. Persistence direction

Les outputs sont deja provider-neutral :

```text
ProviderInstrumentSnapshot
ProviderQuoteSnapshot
ProviderAccountSnapshot
ProviderPositionSnapshot
```

Ils pourront donc etre consommes ensuite par :

```text
reconciliation services
portfolio projections
risk snapshots
observability
audit
```

sans importer Alpaca.

---

## 36. Readiness evolution

LOT-05 produisait :

```text
READY_FOR_STARTUP
```

mais :

```text
trading_ready = false
```

LOT-08 apporte les prerequisites read-side permettant au prochain lot de faire :

```text
reference validation
account snapshot
position snapshot
order reconciliation
stream readiness
```

avant de declarer le runtime reellement trading-ready.

---

## 37. Real PAPER evidence

Les tests n'utilisent aucun credential reel.

Avant release :

```text
asset read
IEX latest quote
account read
positions read
```

devront etre observes contre le vrai compte PAPER attendu.

---

## 38. LOT-08 result

```text
canonical Quote                 YES
ProviderQuoteSnapshot          YES
static reference resolver      YES
asset/reference read           YES
IEX latest quote               YES
account snapshot               YES
position snapshots             YES
read-only boundary             YES
ExecutionPort changed          NO
economic writes                NO
```

---

## 39. Next lot

Le prochain lot peut maintenant orchestrer :

```text
LOT-09 - Startup, Restart & End-to-End Reconciliation
```

avec :

```text
load local unresolved state
load provider account
load provider positions
load provider orders
start trade_updates
reconcile
only then declare TRADING_READY
```

---

## 40. Final principle

> Economic commands and provider observations are separate paths. LOT-08 makes Alpaca observations canonical without giving the read-side any power to trade.
