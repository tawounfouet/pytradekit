# 43 - PyTradeKit - Provider Comparative Architecture

**Projet :** PyTradeKit  
**Document :** Architecture comparative des providers  
**Version :** 1.0  
**Date :** 2026-10-22  
**Statut :** Architecture gate avant LOT-05  
**Providers étudiés :** Alpaca, Binance Spot, Interactive Brokers, Pepperstone + cTrader  
**Documents sources :** `39`, `40`, `41`, `42`  
**Milestone d'implémentation immédiat :** `0.5.x - Persistence + Alpaca Paper`

---

## 1. Objet du document

Ce document consolide les quatre études provider réalisées pour PyTradeKit :

```text
39 - Alpaca API & SDK Integration Analysis
40 - Binance Spot API & SDK Integration Analysis
41 - IBKR API & SDK Integration Analysis
42 - Pepperstone + cTrader API & SDK Integration Analysis
```

Son objectif n'est plus de comprendre un provider isolé.

Son objectif est de décider l'architecture commune de PyTradeKit après confrontation de quatre familles structurellement différentes :

```text
Alpaca
    broker equities moderne
    REST + WebSocket
    PAPER / LIVE

Binance Spot
    crypto exchange
    REST + WebSocket API + Market Streams + User Data Stream
    Demo / Testnet / LIVE

IBKR
    broker multi-asset
    TWS API via IB Gateway / TWS
    Web API
    stateful sessions
    PAPER / LIVE

Pepperstone + cTrader
    broker + trading platform
    cTrader Open API
    cTrader FIX API
    cBots
    Forex / CFD
    Demo / LIVE
```

La question centrale devient :

> Quelles abstractions appartiennent réellement au noyau canonique de PyTradeKit, quelles abstractions appartiennent à l'Application et au Runtime, et quelles notions doivent rester strictement provider-specific ?

---

## 2. Pourquoi ce gate est nécessaire avant LOT-05

Sans cette étape, il serait facile de construire :

```text
AlpacaAdapter
```

puis de laisser progressivement le core adopter des concepts Alpaca :

```text
paper bool
client_order_id semantics
US equity assumptions
position model
market clock assumptions
REST-oriented runtime
```

Le résultat serait un framework prétendument multi-provider mais réellement :

```text
Alpaca-shaped
```

Les études Binance, IBKR et cTrader ont précisément servi à casser cette illusion.

Le gate doit maintenant figer :

```text
canonical semantics
provider identities
execution certainty
capability model
constraint model
runtime boundaries
persistence mappings
safety rules
reconciliation rules
```

avant d'implémenter le runtime Alpaca PAPER final.

---

## 3. Conclusion exécutive

La conclusion principale est :

> PyTradeKit ne doit pas construire un super broker universel. Il doit normaliser les sémantiques économiques communes et préserver les réalités opérationnelles de chaque provider dans l'Application, le Runtime, l'ACL et le Transport.

L'architecture cible devient :

```text
                         PYTRADEKIT DOMAIN
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
            OMS             Portfolio             Risk
             |                  |                  |
             +------------------+------------------+
                                |
                                v
                        APPLICATION PORTS
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
          Execution Provider          Market Data Provider
                  |                           |
                  +-------------+-------------+
                                |
                                v
                         PROVIDER ACL
                                |
          +-------------+-------+-------+-------------+
          |             |               |             |
          v             v               v             v
       Alpaca         Binance          IBKR         cTrader
          |             |               |             |
          v             v               v             v
     REST / WS      REST / WS      Gateway / Web   Open API / FIX
```

Le Domain reste ignorant de :

```text
alpaca-py
binance-sdk-spot
ib_async
ibapi
ctrader_open_api
Twisted
Protobuf
FIX
HTTP
WebSocket
TCP
OAuth
API keys
clientId
conId
symbolId
```

---

## 4. Décisions architecturales principales

Les décisions suivantes sont retenues par ce document.

### D-01 - Le Domain reste provider-neutral

Statut :

```text
ACCEPTED
```

Aucun type SDK ou protocole provider ne doit entrer dans :

```text
Domain Entities
Domain Value Objects
Domain Events
Domain Services
```

---

### D-02 - Command et Fact restent séparés

Statut :

```text
ACCEPTED
```

Un appel de soumission :

```text
submit order
```

est une commande.

Une exécution :

```text
fill
partial fill
cancel confirmation
reject
```

est un fait.

Les deux chemins doivent être modélisés séparément.

---

### D-03 - No blind retry sur les commandes économiques

Statut :

```text
ACCEPTED
```

Une erreur réseau ou un timeout après émission d'une commande ne prouve pas que le provider n'a rien exécuté.

Donc :

```text
unknown outcome
-> UNCERTAIN
-> reconcile
```

et jamais :

```text
unknown outcome
-> automatic second economic submit
```

---

### D-04 - `ExecutionCertainty` est provider-agnostic

Statut :

```text
ACCEPTED
```

Les quatre providers justifient une notion explicite de certitude d'effet distant.

---

### D-05 - `ClientOrderReference` est un concept commun

Statut :

```text
ACCEPTED
```

Correspondances :

```text
Alpaca   -> client_order_id
Binance  -> newClientOrderId
IBKR     -> orderRef / cOID
cTrader  -> clientOrderId / FIX ClOrdID
```

La sémantique exacte de duplication et d'unicité reste provider-specific.

---

### D-06 - Les IDs provider ne remplacent jamais les IDs canoniques

Statut :

```text
ACCEPTED
```

PyTradeKit conserve :

```text
OrderId
FillId
InstrumentId
AccountId
```

Les IDs provider servent à :

```text
correlation
reconciliation
audit
support
```

---

### D-07 - `ProviderOrderIdentity` doit pouvoir porter plusieurs niveaux d'identité

Statut :

```text
ACCEPTED
```

IBKR démontre qu'un simple `external_order_id` est insuffisant.

Le modèle doit pouvoir représenter :

```text
client reference
session order ID
provider order ID
permanent order ID
account scope
session scope
```

---

### D-08 - `ExternalFillId` / `ProviderFillIdentity` est une primitive de déduplication

Statut :

```text
ACCEPTED
```

Exemples :

```text
Alpaca   -> execution identity
Binance  -> tradeId
IBKR     -> execId
cTrader  -> dealId
```

---

### D-09 - `Balance` reste distinct de `Position`

Statut :

```text
ACCEPTED
```

Binance rend cette séparation indispensable.

IBKR et cTrader la confirment avec les notions de cash, margin, assets et account state.

---

### D-10 - `InstrumentTradingConstraints` devient une abstraction commune

Statut :

```text
ACCEPTED AS APPLICATION/REFERENCE CONTRACT
```

Mais elle ne doit pas devenir une collection de tous les champs de tous les providers.

---

### D-11 - `ProviderSession` appartient au Runtime, pas au Domain

Statut :

```text
ACCEPTED
```

IBKR et cTrader rendent cette notion indispensable.

Alpaca et Binance peuvent aussi utiliser une session runtime même si leur transport est plus proche d'un client distant stateless.

---

### D-12 - `ExecutionProvider` est le terme générique cible

Statut :

```text
ACCEPTED AS TERMINOLOGY
```

Il est plus général que :

```text
Broker
```

car :

```text
Binance = exchange
cTrader = platform
Pepperstone = broker
IBKR = broker + routing infrastructure
```

Le renommage de public APIs existantes n'est pas obligatoire dans 0.5.

---

### D-13 - `ExecutionProvider` et `MarketDataProvider` sont séparables

Statut :

```text
ACCEPTED
```

Un runtime doit pouvoir utiliser :

```text
IBKR execution
+
external market data
```

ou :

```text
Alpaca execution
+
other data source
```

sans réécrire le Domain.

---

### D-14 - `PositionAccountingMode` est réel mais différé

Statut :

```text
DEFERRED TO FX/CFD EXPANSION
```

cTrader introduit :

```text
HEDGED
NETTED
```

Le core 0.5 n'a pas besoin de l'introduire immédiatement.

---

### D-15 - Margin, leverage et financing sont réels mais différés

Statut :

```text
DEFERRED TO 1.2.x
```

Ne pas ajouter prématurément :

```text
MarginAccountSnapshot
FinancingCharge
ContractSize
PipSize
```

au milestone Alpaca 0.5.

---

## 5. Les quatre providers comme stress tests

Chaque provider challenge une dimension différente.

```text
Alpaca
    -> hosted broker API
    -> equities
    -> PAPER
    -> command REST + fact stream

Binance
    -> crypto exchange
    -> 24/7
    -> symbol filters
    -> weighted rate limits
    -> asset balances

IBKR
    -> stateful local gateway
    -> client/order ID sequencing
    -> contract qualification
    -> multi-asset
    -> market data entitlements

cTrader/Pepperstone
    -> broker/platform separation
    -> FX/CFD
    -> HEDGED/NETTED
    -> leverage/margin/swap
    -> OAuth + Protobuf + FIX
```

Un concept commun qui survit aux quatre est un bon candidat pour PyTradeKit.

---

## 6. Principe de normalisation

Le principe directeur est :

> Normalize semantics, not provider features.

Cela signifie :

```text
normalize:
Order
Fill
Position
Balance
Instrument
Execution certainty
Canonical identities
```

mais conserver :

```text
provider-specific constraints
provider-specific IDs
provider-specific transport
provider-specific session lifecycle
provider-specific rate limits
provider-specific account topology
provider-specific market-data entitlements
```

---

## 7. Anti-pattern - Lowest Common Denominator

Il serait dangereux de réduire tous les providers à :

```text
submit_order()
cancel_order()
get_positions()
```

sans représenter :

```text
capabilities
constraints
uncertainty
account context
provider identities
```

Cela produit une abstraction trop faible.

---

## 8. Anti-pattern - Universal Provider Object

Éviter :

```text
UniversalBroker
```

avec :

```text
hundreds of optional fields
if provider == ...
```

Le design doit préférer :

```text
small canonical contracts
+
provider-specific ACL
+
capability discovery
```

---

## 9. Architecture par couches

L'architecture comparative retient six couches principales :

```text
1. Domain
2. Application
3. Runtime
4. Persistence
5. Provider ACL
6. Transport / SDK
```

---

## 10. Domain

Le Domain porte :

```text
Order
Fill
Position
Balance
Portfolio
Risk
Instrument
Money
Price
Quantity
Percentage
Canonical IDs
Domain Events
```

Le Domain ne porte pas :

```text
API token
HTTP status
SDK exception
rate-limit header
WebSocket reconnect
TWS clientId
Binance recvWindow
cTrader symbolId
```

---

## 11. Application

L'Application orchestre :

```text
use cases
ports
provider-neutral integration contracts
identity mappings
capabilities
constraints
command dispatch
fact ingestion
reconciliation workflows
```

---

## 12. Runtime

Le Runtime porte :

```text
provider sessions
connections
readiness
health
reconnect
rate/pacing state
clock offsets
timeouts
retry policy
secret resolution
environment safety
provider lifecycle
```

---

## 13. Persistence

La Persistence porte :

```text
canonical repositories
provider identity mappings
Inbox
Outbox
UnitOfWork
runtime metadata where durable recovery requires it
```

---

## 14. Provider ACL

L'Anti-Corruption Layer porte :

```text
provider models
mappers
error translation
capability extraction
constraint extraction
account snapshots
provider commands
provider events
```

---

## 15. Transport

Le Transport porte :

```text
REST
WebSocket
TCP
FIX
Protobuf
OAuth
signatures
SDK clients
heartbeat
sequence numbers
```

---

## 16. Dependency direction

La règle est :

```text
Domain
  ^
  |
Application
  ^
  |
Runtime / Persistence / Provider ACL
  ^
  |
Transport / SDK
```

Jamais :

```text
Domain -> SDK
Domain -> HTTP
Domain -> Protobuf
Domain -> SQLAlchemy
```

---

## 17. Provider taxonomy

PyTradeKit doit distinguer trois axes.

```text
Economic intermediary
Trading platform
Technical transport
```

Exemples :

```text
Alpaca:
    intermediary/platform = Alpaca
    transport = REST/WS

Binance:
    venue/platform = Binance
    transport = REST/WS

IBKR:
    intermediary = IBKR
    platform/gateway = TWS or IB Gateway
    transport = TWS TCP or Web API

Pepperstone+cTrader:
    intermediary = Pepperstone
    platform = cTrader
    transport = Open API or FIX
```

---

## 18. `ExecutionProvider` terminology

Le terme recommandé pour les ports de trading externes est :

```text
ExecutionProvider
```

Cela évite de forcer :

```text
Broker
```

sur Binance ou cTrader.

---

## 19. Renommage des APIs existantes

Décision :

```text
DO NOT FORCE A BROAD PUBLIC RENAME IN 0.5
```

Si le code courant possède déjà des ports stables :

```text
ExecutionPort
BrokerPort
```

ils ne doivent pas être renommés uniquement pour satisfaire le vocabulaire du document.

Le changement peut être :

```text
incremental
backward-compatible
```

---

## 20. Canonical OrderId

`OrderId` reste :

```text
owned by PyTradeKit
```

Il est créé avant l'appel provider.

---

## 21. Pourquoi l'OrderId doit précéder le provider

Il permet de persister :

```text
intent
risk decision
provider client reference
submission state
```

avant l'effet réseau.

---

## 22. ClientOrderReference

Proposition :

```text
ClientOrderReference
    value: str
```

avec :

```text
non-empty
bounded length at adapter boundary
stable for one canonical Order
```

---

## 23. Scope du ClientOrderReference

La portée exacte d'unicité dépend du provider.

Donc PyTradeKit ne doit pas prétendre :

```text
globally unique forever
```

Le Runtime peut générer une valeur suffisamment forte.

---

## 24. Mapping des références

```text
Alpaca   client_order_id
Binance  newClientOrderId
IBKR     orderRef / cOID
cTrader  clientOrderId / ClOrdID
```

---

## 25. ProviderOrderIdentity

Proposition application/persistence :

```text
ProviderOrderIdentity
    provider
    account_identity
    client_reference
    provider_order_id
    session_order_id optional
    permanent_order_id optional
    provider_session_reference optional
```

---

## 26. Pourquoi plusieurs IDs

IBKR peut produire :

```text
clientId
orderId
permId
orderRef
```

cTrader produit :

```text
clientOrderId
orderId
```

FIX produit :

```text
ClOrdID
OrderID
```

Un seul champ générique serait ambigu.

---

## 27. ProviderFillIdentity

Proposition :

```text
ProviderFillIdentity
    provider
    account_identity
    external_fill_id
```

---

## 28. Fill identity mappings

```text
Alpaca   -> execution identity
Binance  -> tradeId
IBKR     -> execId
cTrader  -> dealId
```

---

## 29. Fill deduplication invariant

```text
same provider economic execution
received N times
=> one canonical economic effect
```

---

## 30. ProviderAccountIdentity

Proposition :

```text
ProviderAccountIdentity
    provider
    broker optional
    environment
    external_account_id
```

---

## 31. Provider account examples

```text
Alpaca account ID
Binance account context
IBKR account code
cTrader ctidTraderAccountId
```

---

## 32. Account identity is not user identity

Ne pas confondre :

```text
OAuth user
API key owner
broker login
trading account
```

---

## 33. ProviderInstrumentMapping

PyTradeKit possède déjà une notion d'Instrument mapping dans ses fondations.

Le comparatif confirme qu'elle doit supporter :

```text
provider
broker optional
environment
external instrument ID
external symbol
venue/context
validity metadata
```

---

## 34. Instrument identity examples

```text
Alpaca   -> asset/symbol/provider ID
Binance  -> BTCUSDT
IBKR     -> conId
cTrader  -> symbolId + broker/server scope
```

---

## 35. Symbol is never canonical identity

Règle :

```text
InstrumentId != provider symbol
```

---

## 36. Instrument mapping scope

Une mapping key peut dépendre de :

```text
provider
broker
environment
venue
account/server context
```

---

## 37. InstrumentTradingConstraints

Contrat proposé :

```text
InstrumentTradingConstraints
    instrument_id
    observed_at
    min_quantity optional
    max_quantity optional
    quantity_increment optional
    min_price optional
    max_price optional
    price_increment optional
    min_notional optional
    max_notional optional
    supported_order_types
    supported_time_in_force
```

---

## 38. Constraints provider examples

```text
Binance:
    PRICE_FILTER
    LOT_SIZE
    MIN_NOTIONAL

IBKR:
    minTick
    MarketRule
    minSize
    sizeIncrement

cTrader:
    minVolume
    maxVolume
    stepVolume
    pipPosition
    maxExposure

Alpaca:
    asset/order capabilities
    price/order rules
```

---

## 39. Static vs dynamic constraints

Toutes les contraintes ne sont pas statiques.

Exemples :

```text
Binance PERCENT_PRICE
IBKR price-dependent market rules
broker account access restrictions
```

Donc le modèle doit permettre :

```text
static canonical snapshot
+
provider final validation
```

---

## 40. Constraint authority

Même avec validation locale :

```text
provider remains final authority
```

---

## 41. Constraint refresh pattern

```text
local validation
    |
    v
remote submit
    |
    X constraint reject
    |
    v
refresh constraints
    |
    v
surface rejection
```

Ne pas auto-resoumettre.

---

## 42. Price quantization

Le core ne doit pas silencieusement arrondir une intention invalide.

Default :

```text
REJECT
```

Une policy explicite pourra permettre :

```text
ROUND_DOWN
ROUND_NEAREST
```

plus tard.

---

## 43. Quantity quantization

Même règle pour :

```text
stepSize
sizeIncrement
stepVolume
```

---

## 44. Pip vs tick

cTrader démontre que :

```text
pip
```

et :

```text
tick
```

ne sont pas nécessairement identiques.

Ce concept est différé à 1.2.

---

## 45. Contract size

Le besoin devient explicite pour FX/CFD.

Statut :

```text
DEFERRED TO 1.2
```

---

## 46. Order types canonical baseline

Le minimum commun à qualifier est :

```text
MARKET
LIMIT
CANCEL
QUERY
```

---

## 47. Advanced order types

Ne pas forcer dans 0.5 :

```text
STOP
STOP_LIMIT
OCO
OTO
TRAILING
PEGGED
provider algos
```

---

## 48. Capability-driven advanced orders

Le futur modèle doit permettre :

```text
provider supports feature X
```

sans ajouter automatiquement un nouveau Domain aggregate.

---

## 49. Command side

Canonical flow :

```text
Order intent
    |
    v
Validation
    |
    v
Risk
    |
    v
Provider capability/constraint validation
    |
    v
Persist order + client reference
    |
    v
Controlled provider submit
```

---

## 50. Fact side

```text
Provider event
    |
    v
Transport receiver
    |
    v
Inbox
    |
    v
Provider event mapper
    |
    v
Canonical fact
    |
    v
OMS / Portfolio
```

---

## 51. Provider fact sources

```text
Alpaca
    trade_updates

Binance
    executionReport

IBKR
    openOrder / orderStatus / execDetails

cTrader
    ProtoOAExecutionEvent
    FIX ExecutionReport
```

---

## 52. Fact authority

Une réponse de submit n'est pas nécessairement la vérité finale.

---

## 53. Partial fills

Les quatre providers justifient :

```text
PARTIALLY_FILLED
multiple Fill records
cumulative filled quantity
```

---

## 54. Cancel race

Canonical race :

```text
cancel requested
    |
    +-----------+
    |           |
    v           v
CANCELED      FILL
```

L'OMS doit accepter le fact provider réellement arrivé.

---

## 55. Rejection

Un reject doit conserver :

```text
canonical category
provider code
provider message
```

---

## 56. ExecutionCertainty

Proposition :

```text
ExecutionCertainty
    CERTAIN_NOT_SENT
    CERTAIN_ACCEPTED_OR_REJECTED
    UNCERTAIN
```

La forme exacte de l'enum peut être simplifiée selon le code actuel.

---

## 57. UNCERTAIN trigger examples

```text
Alpaca
    timeout / network failure after send

Binance
    -1007 TIMEOUT
    HTTP 5XX unknown status

IBKR
    socket/gateway disconnect around placeOrder

cTrader
    response timeout/disconnect after message send
```

---

## 58. No blind retry invariant

```text
one canonical submit intent
must not silently become
multiple economic submissions
```

---

## 59. Retry classes

Runtime classification :

```text
SAFE_READ_RETRY
IDEMPOTENT_TRANSPORT_RETRY
ECONOMIC_COMMAND_NO_RETRY
UNKNOWN_OUTCOME_RECONCILE
```

---

## 60. SDK retry policy

Les SDK defaults ne sont pas des policies métier.

Exemples :

```text
Alpaca REST retries
Binance REST retries
IBKR reconnect behavior
cTrader reconnect/queue behavior
```

doivent être explicitement contrôlés.

---

## 61. Provider session

Proposition Runtime :

```text
ProviderSession
    connect()
    authenticate()
    ready()
    health()
    disconnect()
```

---

## 62. ProviderSession is not universal transport

Les implémentations diffèrent :

```text
Alpaca
    API clients + streams

Binance
    REST + private/public WS

IBKR
    TWS/IB Gateway session

cTrader
    TLS + application auth + account auth
```

---

## 63. Runtime readiness

Readiness doit signifier :

```text
safe to execute intended operation
```

pas seulement :

```text
socket is open
```

---

## 64. Readiness Alpaca

Exemple :

```text
credentials resolved
PAPER endpoint verified
account accessible
stream state known
snapshot loaded
```

---

## 65. Readiness Binance

```text
Demo/Testnet endpoint verified
account authenticated
server time usable
exchangeInfo loaded
constraints loaded
User Data Stream connected if required
reconciliation complete
```

---

## 66. Readiness IBKR

```text
Gateway/TWS reachable
protocol handshake complete
nextValidId received
expected account verified
reconciliation complete
```

---

## 67. Readiness cTrader

```text
TLS connected
application authenticated
expected account discovered
account authenticated
Demo environment verified
snapshots loaded
reconciliation complete
```

---

## 68. Readiness domains

À terme, un runtime peut distinguer :

```text
ExecutionReady
MarketDataReady
PortfolioReady
```

---

## 69. ProviderEnvironment

Proposition Runtime :

```text
ProviderEnvironment
    provider
    environment_name
    transport
    endpoint
```

---

## 70. RuntimeSafetyMode

Une couche globale peut exprimer :

```text
SANDBOX
LIVE
```

ou :

```text
SIMULATED
SANDBOX
LIVE
```

---

## 71. Provider-specific environments

```text
Alpaca
    PAPER / LIVE

Binance
    DEMO / TESTNET / LIVE

IBKR
    PAPER / LIVE

cTrader
    DEMO / LIVE
```

---

## 72. Do not flatten environment semantics

Ne pas introduire un enum global :

```text
PAPER
```

et prétendre qu'il signifie la même chose partout.

---

## 73. Safety mapping

Exemple :

```text
Alpaca PAPER      -> SANDBOX
Binance Demo      -> SANDBOX
Binance Testnet   -> SANDBOX
IBKR PAPER        -> SANDBOX
cTrader Demo      -> SANDBOX
```

---

## 74. Fail closed

Toute incohérence :

```text
safety mode SANDBOX
+
LIVE endpoint
```

provoque :

```text
startup failure
```

---

## 75. No LIVE fallback

Jamais :

```text
missing endpoint
=> default LIVE
```

---

## 76. SecretsPort

Tous les providers justifient :

```text
SecretsPort
```

---

## 77. Secret classes

```text
API key
API secret
OAuth client secret
access token
refresh token
broker password
private key
FIX password
```

---

## 78. Secret references

Config visible :

```text
secret://provider/environment/name
```

et non :

```text
raw secret
```

---

## 79. Redaction invariant

Secrets must not appear in :

```text
logs
repr
exceptions
metrics
fixtures
Git commits
```

---

## 80. Capability model

Une capability répond :

```text
Can this provider/account/instrument/transport perform operation X?
```

---

## 81. CapabilityContext

Proposition Application :

```text
CapabilityContext
    provider
    broker optional
    environment
    transport optional
    account_identity optional
    instrument_id optional
    venue optional
```

---

## 82. Capability hierarchy

Capabilities peuvent provenir de :

```text
platform
broker
account
instrument
transport
market-data subscription
```

---

## 83. Capability examples

```text
MARKET_ORDER
LIMIT_ORDER
CANCEL
ORDER_QUERY
REALTIME_QUOTES
HISTORICAL_BARS
PARTIAL_FILLS
EXTENDED_HOURS
HEDGED_POSITIONS
NETTED_POSITIONS
```

---

## 84. Capability vs constraint

```text
Capability:
    operation supported?

Constraint:
    under which limits is it valid?
```

---

## 85. Market data is separate

Le comparatif confirme :

```text
ExecutionProvider
!=
MarketDataProvider
```

---

## 86. Market data capability dimensions

```text
historical
latest snapshot
realtime stream
quotes
trades
bars
depth
feed quality
entitlement
```

---

## 87. Market data feed quality

Exemples :

```text
Alpaca IEX vs SIP
IBKR realtime vs delayed/frozen
cTrader broker feed
Binance exchange streams
```

---

## 88. MarketDataObservation metadata

Toute observation devrait pouvoir porter :

```text
provider_timestamp
received_at
source/feed
freshness metadata
```

---

## 89. Time semantics

Canonical timestamps :

```text
UTC
```

---

## 90. Provider timezone must be normalized correctly

Ne jamais :

```text
strip timezone
then mark UTC
```

---

## 91. Provider clock offset

Binance rend utile un concept Runtime :

```text
ProviderClockOffset
```

Il ne doit pas entrer dans le Domain.

---

## 92. ClockPort vs ProviderClockOffset

```text
ClockPort
    canonical application time dependency

ProviderClockOffset
    infrastructure observation for signed transport
```

---

## 93. Rate limit / pacing model

Ce modèle appartient au Runtime.

---

## 94. Why no universal scalar

Les providers exposent :

```text
Alpaca
    endpoint/API plan limits

Binance
    request weight
    IP limits
    order counts

IBKR
    pacing
    market data lines

cTrader
    requests/s
    historical request limits
    local SDK queue
```

---

## 95. ProviderRateLimitState

Proposition Runtime :

```text
ProviderRateLimitState
    provider
    dimensions
    retry_after optional
    observed_at
    status
```

---

## 96. RateLimit dimensions remain provider-specific

Le champ :

```text
dimensions
```

peut être un type provider infrastructure, pas un Domain dict arbitraire.

---

## 97. Backoff is not economic retry

Après 429 :

```text
wait
```

ne signifie pas :

```text
repeat unknown order submission
```

---

## 98. Account model comparative

```text
Alpaca
    account + cash + positions

Binance
    free/locked asset balances

IBKR
    cash + positions + account values + margin

cTrader
    balance + equity + positions + leverage/margin + account mode
```

---

## 99. Balance remains canonical

`Balance` doit rester une primitive de premier rang.

---

## 100. Position remains canonical

`Position` doit représenter l'exposition d'un instrument selon les semantics du Portfolio.

---

## 101. Position accounting challenge

cTrader démontre que le provider peut être :

```text
HEDGED
```

ou :

```text
NETTED
```

---

## 102. PositionAccountingMode status

Décision :

```text
DESIGN EXTENSION POINT NOW
IMPLEMENT LATER
```

---

## 103. 0.5 portfolio semantics

Alpaca PAPER peut continuer à utiliser le modèle actuel sans introduire toute la complexité HEDGED/NETTED.

---

## 104. Account snapshot vs Domain state

Un provider account snapshot est :

```text
external observation
```

Il ne doit pas être confondu avec :

```text
canonical Portfolio aggregate
```

---

## 105. ProviderAccountSnapshot

Application model possible :

```text
ProviderAccountSnapshot
    account_identity
    balances
    positions
    capabilities
    provider metadata
    observed_at
```

---

## 106. Margin snapshot

Statut :

```text
DEFERRED
```

jusqu'à IBKR/cTrader expansion.

---

## 107. Financing / swap

Statut :

```text
DEFERRED TO FX/CFD
```

Un swap n'est ni un Fill ni une Commission.

---

## 108. AccountActivity future extension

Concept potentiel :

```text
AccountActivity
```

pour :

```text
deposit
withdrawal
swap
interest
corporate action
fee adjustment
```

Non requis en 0.5.

---

## 109. Fee semantics

Le comparatif révèle qu'une fee peut être :

```text
cash amount
asset quantity
late execution enrichment
separate commission event
```

---

## 110. Universal Fee model status

```text
NOT FROZEN
```

Ne pas sur-généraliser maintenant.

---

## 111. Portfolio ownership

PyTradeKit doit distinguer :

```text
orders owned by PyTradeKit
```

et :

```text
account-wide economic state
```

---

## 112. Why ownership matters

IBKR et cTrader permettent :

```text
manual orders
other API clients
other bots
```

Binance et Alpaca peuvent également être utilisés par plusieurs actors.

---

## 113. Initial ownership policy

PyTradeKit gère activement :

```text
orders carrying known canonical mapping/client reference
```

mais observe :

```text
account-wide balances and positions
```

---

## 114. External activity policy

Une position externe doit :

```text
influence risk
influence reconciliation
```

même si PyTradeKit ne possède pas l'ordre qui l'a créée.

---

## 115. Inbox

Inbox is now a cross-provider invariant.

---

## 116. Inbox purpose

```text
at-least-once provider event delivery
+
idempotent local handling
```

---

## 117. Outbox

Outbox guarantees durable publication of local domain/application events after transaction commit.

---

## 118. UnitOfWork

UnitOfWork enables atomic local mutation :

```text
Inbox claim
Order mutation
Fill insert
Portfolio mutation
Outbox record
```

---

## 119. Remote side effect is outside local ACID

No local database transaction can include :

```text
provider order submit
```

as an ACID participant.

---

## 120. Distributed transaction reality

Therefore PyTradeKit needs :

```text
persistence before command
certainty state
event idempotency
reconciliation
```

---

## 121. Reconciliation as first-class behavior

Reconciliation is not exceptional cleanup.

It is a normal distributed-system behavior.

---

## 122. Reconciliation triggers

```text
startup
reconnect
uncertain submit
stream gap
provider mismatch
manual/external activity
constraint drift
```

---

## 123. Order reconciliation

```text
local unresolved order
    |
    v
provider query / snapshot
    |
    v
identity match
    |
    v
converge OMS state
```

---

## 124. Execution reconciliation

Use provider execution identities to recover missing Fill records.

---

## 125. Portfolio reconciliation

Compare :

```text
local portfolio state
vs
provider positions/balances
```

with explicit reconciliation policy.

---

## 126. Reconnect is not reconciliation

```text
transport reconnect
!=
state recovery
```

---

## 127. Provider-specific reconnect examples

```text
Alpaca stream reconnect
Binance WS reconnect
IBKR Gateway/TWS reconnect
cTrader TLS reconnect + reauth
```

---

## 128. Reconnect flow

Canonical pattern :

```text
DISCONNECTED
    |
    v
CONNECT
    |
    v
AUTHENTICATE
    |
    v
RESTORE SUBSCRIPTIONS
    |
    v
RECONCILE
    |
    v
READY
```

---

## 129. Error taxonomy

PyTradeKit needs provider-neutral error categories.

---

## 130. Canonical provider error families

```text
AuthenticationError
AuthorizationError
TradingDisabledError
InvalidInstrumentError
InvalidOrderError
ProviderRejectedOrderError
RateLimitedError
ProviderUnavailableError
ProviderProtocolError
UnknownSubmissionOutcomeError
```

---

## 131. Preserve raw diagnostic

Mapped errors should preserve :

```text
provider code
provider message
request/correlation metadata
```

outside the Domain.

---

## 132. HTTP status is not business status

Binance and IBKR Web API make this explicit.

Do not map solely from :

```text
HTTP status
```

---

## 133. Provider error code examples

```text
Binance -1007
IBKR numeric callback codes
cTrader protocol error codes
Alpaca HTTP/API errors
```

must be mapped conservatively.

---

## 134. Persistence architecture

Canonical tables/repositories remain provider-neutral.

---

## 135. Do not add provider columns everywhere

Avoid :

```text
orders.alpaca_order_id
orders.binance_order_id
orders.ibkr_perm_id
orders.ctrader_order_id
```

---

## 136. Provider mapping persistence

Prefer :

```text
provider_order_mappings
provider_instrument_mappings
provider_account_mappings
```

or equivalent typed structures.

---

## 137. ProviderOrderMapping fields

Candidate :

```text
canonical_order_id
provider
account_identity
client_reference
provider_order_id
session_order_id
permanent_order_id
provider_session_reference
created_at
updated_at
```

---

## 138. Fill provider mapping

Candidate :

```text
canonical_fill_id
provider
account_identity
external_fill_id
```

with unique constraint.

---

## 139. Instrument mapping persistence

Candidate :

```text
instrument_id
provider
broker optional
environment
external_id
external_symbol
venue
valid_from
valid_to
```

---

## 140. Runtime metadata persistence

Persist only what recovery requires.

Examples :

```text
provider session identity if needed
IBKR clientId/order sequence association
FIX sequence state if implemented later
```

---

## 141. Do not persist ephemeral SDK objects

Never persist :

```text
TradingClient object
Twisted Deferred
WebSocket object
IB Contract instance
```

---

## 142. Architecture package topology

Recommended high-level topology :

```text
pytradekit/
|
+-- domain/
|
+-- execution/
|   +-- ports/
|   +-- application/
|
+-- portfolio/
|
+-- risk/
|
+-- market_data/
|
+-- providers/
|   +-- alpaca/
|   +-- binance/
|   +-- ibkr/
|   +-- ctrader/
|
+-- persistence/
|
+-- runtime/
```

---

## 143. Provider package structure

Each provider may have :

```text
config.py
session.py
execution.py
events.py
snapshots.py
capabilities.py
constraints.py
errors.py
market_data/
mappers/
transport/
```

as needed.

---

## 144. No forced identical provider package

Do not create empty modules merely to make all providers look identical.

---

## 145. Alpaca package likely needs

```text
execution.py
trade_updates.py
snapshots.py
market_data.py
capabilities.py
mappers/
```

---

## 146. Binance package likely needs

```text
execution.py
user_data_stream.py
constraints.py
rate_limits.py
clock_sync.py
market_data/
mappers/
```

---

## 147. IBKR package likely needs

```text
session.py
gateway.py
execution.py
order_events.py
contracts.py
market_rules.py
snapshots.py
market_data/
mappers/
```

---

## 148. cTrader package likely needs

```text
session.py
auth.py
execution.py
execution_events.py
constraints.py
snapshots.py
market_data/
transport/
mappers/
```

---

## 149. Provider SDK isolation fitness functions

```text
No alpaca imports outside Alpaca adapter
No Binance SDK imports outside Binance adapter
No ib_async/ibapi imports outside IBKR adapter
No ctrader_open_api/Twisted imports outside cTrader adapter
```

---

## 150. Transport isolation

No public contract may expose :

```text
HTTP response
WebSocket payload
FIX message
Protobuf message
Twisted Deferred
IB Contract
```

---

## 151. Capability extraction

Provider-specific metadata is translated into canonical capabilities where semantics align.

---

## 152. Constraint extraction

Provider-specific numeric limits are translated into canonical constraints where semantics align.

---

## 153. Preserve provider extension data

Not all fields should be normalized.

Provider diagnostics can retain typed provider metadata inside infrastructure.

---

## 154. Avoid arbitrary dicts in Domain

Do not add :

```text
metadata: dict[str, Any]
```

as a shortcut for provider leakage in core entities.

---

## 155. Observability model

Provider adapters should emit structured metrics and logs.

---

## 156. Common metrics

```text
provider_requests_total
provider_errors_total
provider_submit_total
provider_submit_uncertain_total
provider_reconnect_total
provider_events_received_total
provider_duplicate_events_total
provider_reconciliation_unresolved_total
```

---

## 157. Provider-specific metrics

Examples :

```text
Binance request weight
IBKR market data lines
cTrader queue depth
Alpaca feed selection
```

---

## 158. Correlation fields

Structured logs may use :

```text
CorrelationId
OrderId
ClientOrderReference
ProviderOrderIdentity
ProviderFillIdentity
InstrumentId
ProviderInstrumentIdentity
```

---

## 159. Sensitive fields

Avoid raw :

```text
account IDs
credentials
tokens
signatures
```

when not necessary.

---

## 160. Compliance suite direction

The existing Broker Adapter Compliance idea should evolve conceptually into :

```text
Provider Adapter Compliance Suite
```

---

## 161. Compliance suite common tests

```text
canonical ID preservation
client reference roundtrip
no float economic mapping
partial fill handling
cancel race
provider error mapping
duplicate fact idempotency
uncertain outcome handling
sandbox safety
secret redaction
```

---

## 162. ExecutionProvider contract tests

A provider implementation should prove :

```text
submit MARKET
submit LIMIT
cancel
query/reconcile
```

for supported capabilities.

---

## 163. Event receiver contract tests

```text
partial fill
full fill
cancel
reject
duplicate event
out-of-order event
```

---

## 164. Account snapshot contract tests

Verify :

```text
account identity
balances
positions
observed_at
```

without assuming identical provider fields.

---

## 165. Constraint contract tests

Verify :

```text
numeric exactness
Decimal conversion
minimums
increments
provider refresh
```

---

## 166. Decimal invariant

All economic values must use exact decimal semantics.

---

## 167. Provider source values

Provider may encode numbers as :

```text
string decimal
integer scaling
double/float SDK fields
```

Adapter must normalize to :

```text
Decimal
```

before canonical use.

---

## 168. Float ban scope

At minimum :

```text
Price
Quantity
Money
fees
balances
notional
margin
```

must not use float as canonical truth.

---

## 169. Market sessions

Do not assume every market is session-based in the same way.

---

## 170. Session examples

```text
US equities
    exchange sessions

Binance Spot
    24/7

FX
    near 24/5 with maintenance/weekend windows
```

---

## 171. MarketCalendar capability

Calendar/session behavior should be driven by market/instrument/provider reference data.

---

## 172. Extended hours

Extended hours support is capability-specific.

---

## 173. Market data and execution calendar may differ

Provider market data may remain available while trading is restricted.

---

## 174. Provider health model

Runtime state can include :

```text
READY
DEGRADED
RECONCILING
DISCONNECTED
AUTH_FAILED
THROTTLED
```

Provider-specific implementations may add internal detail.

---

## 175. Avoid giant global health enum

Not every state belongs to a public universal enum.

Expose only meaningful common health states.

---

## 176. Startup architecture

Canonical startup :

```text
load config
resolve secrets
validate environment safety
initialize persistence
initialize provider session
authenticate
verify account
load capabilities/constraints
load snapshots
reconcile unresolved state
connect event streams
connect required market data
READY
```

---

## 177. Provider-specific startup hooks

```text
Binance
    clock sync

IBKR
    Gateway handshake + nextValidId

cTrader
    app auth + account auth

Alpaca
    PAPER endpoint + account checks
```

---

## 178. Shutdown architecture

```text
stop accepting new commands
flush local durable work
disconnect streams
close provider sessions
close DB resources
```

---

## 179. Shutdown does not cancel provider orders implicitly

Runtime termination must not silently cancel or modify economic state unless explicitly configured.

---

## 180. Provider transport retry vs command retry

Transport may retry :

```text
connect
DNS
read-only query
stream reconnect
```

without granting permission to retry :

```text
order submit
```

---

## 181. Reconciliation truth sources

Provider-specific :

```text
Alpaca
    orders + fills/trade updates + positions

Binance
    orders + user stream + trades + balances

IBKR
    open/completed orders + executions + positions

cTrader
    orders + deals + positions + execution events
```

---

## 182. Provider truth hierarchy

No universal exact hierarchy is frozen.

Each adapter must document its provider truth sources.

---

## 183. Snapshot freshness

Every external snapshot should expose :

```text
observed_at
```

and optionally provider timestamp.

---

## 184. Stale snapshot policy

Risk-sensitive operations can reject when required snapshots exceed a configured age.

---

## 185. Account-wide risk

Long-term risk calculations should use actual provider account exposure when external activity exists.

---

## 186. 0.5 risk boundary

Do not over-expand 0.5 to account-wide margin semantics.

Use the current Alpaca scope.

---

## 187. Live safety is a separate qualification

```text
PAPER/Demo qualified
!=
LIVE qualified
```

for every provider.

---

## 188. Provider qualification levels

Possible future model :

```text
L0 - Unit/contract only
L1 - Sandbox read-only
L2 - Sandbox controlled orders
L3 - Sandbox fault/recovery
L4 - Live approved
```

---

## 189. Sandbox differences must be documented

Examples :

```text
Alpaca PAPER simulation limitations
Binance Demo/Testnet differences
IBKR PAPER fill model differences
cTrader Demo broker conditions
```

---

## 190. Provider manifest

Runtime may expose a diagnostic manifest :

```text
provider
broker optional
environment
transport
sdk
sdk_version
capabilities
qualified_level
```

---

## 191. Provider protocol version

Where meaningful also expose :

```text
protocol/schema version
```

especially for :

```text
cTrader Protobuf
FIX
IBKR TWS API
```

---

## 192. SDK version pinning

Provider dependencies should be optional and pinned during first qualification.

---

## 193. Optional dependency rule

Core install should not require all provider SDKs.

Example future extras :

```text
pytradekit[alpaca]
pytradekit[binance]
pytradekit[ibkr]
pytradekit[ctrader]
```

---

## 194. Provider dependency compatibility

SDK dependency graphs may conflict.

Isolation must remain possible.

---

## 195. Process isolation fallback

If async/runtime libraries conflict :

```text
provider adapter worker process
```

can be used later.

Not default.

---

## 196. Async model

PyTradeKit should expose provider-neutral async contracts where useful.

---

## 197. Twisted isolation

cTrader Twisted must not force Twisted across the whole framework.

---

## 198. Gateway isolation

IB Gateway process lifecycle must not force Gateway semantics into the Domain.

---

## 199. FIX isolation

FIX sequence numbers and session messages stay in Transport/Runtime.

---

## 200. Provider clock isolation

Signed-request time offsets stay in Runtime.

---

## 201. Canonical provider facade

Application-facing structure may consist of several ports rather than one giant facade.

---

## 202. Candidate ports

```text
ExecutionCommandPort
ExecutionQueryPort
ExecutionEventSource
AccountSnapshotPort
MarketDataPort
InstrumentReferencePort
CapabilityProvider
ConstraintProvider
```

---

## 203. Do not create all ports prematurely

Only introduce a port when current implementation or acceptance tests need it.

---

## 204. 0.5 minimal provider contracts

For Alpaca PAPER, likely needed :

```text
Execution command
Execution fact receiver
Account snapshot
Position snapshot
Market data
Capabilities
```

---

## 205. Constraint provider in 0.5

Introduce only if Alpaca implementation concretely needs it.

The architecture should reserve the boundary even if the first implementation is minimal.

---

## 206. ClientOrderReference in 0.5

Recommended to formalize now because it is already critical to :

```text
idempotency
correlation
reconciliation
```

---

## 207. ProviderOrderIdentity in 0.5

Recommended as persistence/application concept even if Alpaca uses a simpler subset.

---

## 208. ProviderFillIdentity in 0.5

Recommended because durable Fill deduplication already exists as a requirement.

---

## 209. ProviderAccountIdentity in 0.5

Recommended at Runtime/Application boundary.

It can remain lightweight.

---

## 210. ProviderSession in 0.5

Do not over-generalize interface.

An Alpaca runtime component may satisfy lifecycle needs without forcing a public abstraction yet.

---

## 211. RuntimeSafetyMode in 0.5

Recommended to hard-lock PAPER.

---

## 212. PositionAccountingMode in 0.5

Do not implement.

Document extension point only.

---

## 213. Margin model in 0.5

Do not implement.

---

## 214. Financing model in 0.5

Do not implement.

---

## 215. FIX model in 0.5

Do not implement.

---

## 216. Binance rate-limit model in 0.5

Do not implement provider-specific dimensions.

Keep Runtime extension point.

---

## 217. IBKR gateway model in 0.5

Do not implement.

---

## 218. cTrader OAuth model in 0.5

Do not implement.

---

## 219. Architecture Decision - canonical now

The following are approved as stable direction :

```text
Canonical IDs remain internal
ClientOrderReference
Provider identity mappings
ExecutionCertainty / UNCERTAIN semantics
No blind retry
Command/fact separation
Inbox/Outbox/UoW
Balance vs Position separation
Provider ACL isolation
Execution vs MarketData separation
Sandbox hard-lock
Reconciliation as first-class
```

---

## 220. Architecture Decision - application/reference contracts

Approved direction :

```text
ProviderAccountIdentity
ProviderOrderIdentity
ProviderFillIdentity
CapabilityContext
InstrumentTradingConstraints
ProviderAccountSnapshot
```

Exact public API can still evolve.

---

## 221. Architecture Decision - runtime only

```text
ProviderSession
ProviderEnvironment
RuntimeSafetyMode
ProviderClockOffset
ProviderRateLimitState
ProviderHealth
Transport retry policy
```

---

## 222. Architecture Decision - deferred Domain extensions

```text
PositionAccountingMode
ContractSize
PipSize
MarginRequirement
FinancingCharge
ExecutionCorrection
AccountActivity
```

---

## 223. Comparative identity matrix

| Concept | Alpaca | Binance Spot | IBKR | cTrader/Pepperstone |
|---|---|---|---|---|
| Canonical OrderId | PyTradeKit | PyTradeKit | PyTradeKit | PyTradeKit |
| Client order reference | `client_order_id` | `newClientOrderId` | `orderRef` / `cOID` | `clientOrderId` / `ClOrdID` |
| Provider order identity | order UUID | `orderId` | `orderId`, `permId` | `orderId` |
| Fill identity | execution identity | `tradeId` | `execId` | `dealId` |
| Instrument identity | asset/symbol mapping | symbol | `conId` | `symbolId` scoped |
| Account identity | provider account | account context | account code | `ctidTraderAccountId` |

---

## 224. Comparative execution matrix

| Dimension | Alpaca | Binance Spot | IBKR | cTrader/Pepperstone |
|---|---|---|---|---|
| Command transport | REST | REST / WS API | TWS TCP / Web API | Open API / FIX |
| Fact channel | `trade_updates` | `executionReport` | callbacks | `ExecutionEvent` / FIX report |
| Partial fills | yes | yes | yes | yes |
| Unknown outcome risk | yes | explicit | yes | yes |
| Client reference | yes | yes | yes | yes |
| Reconciliation | required | required | required | required |

---

## 225. Comparative account matrix

| Dimension | Alpaca | Binance Spot | IBKR | cTrader/Pepperstone |
|---|---|---|---|---|
| Cash/balance | cash/account | asset balances | multi-currency account | balance/equity |
| Position | security position | derived asset holdings | positions | hedged/netted positions |
| Margin | account fields | spot mostly not margin scope | rich margin state | core CFD/FX concept |
| External activity | possible | possible | common | common |
| Financing | limited scope | fee/other activity | margin/interest | swap/rollover |

---

## 226. Comparative constraints matrix

| Provider | Main constraint source |
|---|---|
| Alpaca | asset/order capability and broker rules |
| Binance | `exchangeInfo` filters |
| IBKR | `ContractDetails` + `MarketRule` |
| cTrader | symbol/account metadata |

---

## 227. Comparative session matrix

| Dimension | Alpaca | Binance | IBKR | cTrader |
|---|---|---|---|---|
| Local gateway | no | no | yes for TWS API | no |
| Stateful protocol | streams | streams | strong | strong |
| OAuth | no primary | no primary | Web API | Open API |
| Heartbeat/session | stream-specific | WS-specific | TWS session | Open API/FIX |
| Reauth after reconnect | client-specific | stream-specific | handshake | app/account auth |

---

## 228. Comparative sandbox matrix

```text
Alpaca
    PAPER

Binance
    Demo
    Testnet

IBKR
    PAPER

cTrader
    Demo
```

All map to :

```text
RuntimeSafetyMode.SANDBOX
```

but retain provider-specific environment.

---

## 229. Comparative rate/pacing matrix

```text
Alpaca
    API plan / request limits

Binance
    weighted request limits
    IP limits
    order counters

IBKR
    pacing
    market data lines

cTrader
    requests per second
    historical limits
    SDK local queue
```

---

## 230. Comparative market-data matrix

```text
Alpaca
    historical/latest/stream
    feed choice

Binance
    historical/latest/market streams

IBKR
    entitlement-driven realtime/historical

cTrader
    spots/trendbars/history via broker feed
```

---

## 231. Comparative integration target

```text
0.5 implementation
    Alpaca PAPER

architecture validation only
    Binance Spot
    IBKR
    cTrader/Pepperstone
```

---

## 232. Why Alpaca remains 0.5 target

Alpaca offers the smallest next vertical slice while still exercising :

```text
real remote execution
streaming
PAPER
persistence
reconciliation baseline
market data
```

---

## 233. Why Binance is not 0.5 target

It would add :

```text
crypto asset semantics
symbol filters
weighted rate limits
24/7 market
```

simultaneously.

---

## 234. Why IBKR is not 0.5 target

It would add :

```text
Gateway
session order IDs
contract qualification
market data entitlements
license/runtime complexity
```

---

## 235. Why cTrader is not 0.5 target

It would add :

```text
OAuth
Twisted
Protobuf
FX/CFD
margin
hedging/netting
swap
```

---

## 236. LOT-05 architectural impact

LOT-05 may now proceed with stronger boundaries.

---

## 237. LOT-05 must not hardcode provider semantics

Do not create :

```text
paper: bool
```

as the universal execution environment model.

---

## 238. LOT-05 runtime config

Recommended separation :

```text
RuntimeSafetyMode
+
AlpacaEnvironment
+
AlpacaConfig
```

---

## 239. LOT-05 provider config

Alpaca-specific values remain inside :

```text
providers/alpaca/config.py
```

or equivalent.

---

## 240. LOT-05 secrets

Use :

```text
SecretsPort
```

for API credentials.

---

## 241. LOT-05 client-order reference

Create and persist before remote submit.

---

## 242. LOT-05 provider order mapping

Persist Alpaca provider ID without placing it inside the canonical OrderId.

---

## 243. LOT-05 uncertain state

A transport timeout after send must persist an unresolved/uncertain outcome.

---

## 244. LOT-05 event path

```text
trade_updates
-> Inbox
-> mapper
-> OMS/Fill
-> Portfolio
-> Outbox
```

---

## 245. LOT-05 snapshot path

```text
account
positions
open orders
```

used for startup and reconciliation.

---

## 246. LOT-05 readiness

Do not expose PAPER runtime ready until :

```text
config validated
secrets resolved
PAPER verified
account verified
persistence ready
snapshot loaded
reconciliation complete
required streams ready
```

---

## 247. LOT-05 no automatic LIVE

Hard gate.

---

## 248. LOT-05 no blind SDK retry

Hard gate.

---

## 249. LOT-05 no provider model leakage

Hard gate.

---

## 250. LOT-05 minimal architecture acceptance

```text
[ ] canonical Order remains Alpaca-free
[ ] client reference persisted
[ ] provider order ID mapped separately
[ ] Fill external identity deduplicated
[ ] PAPER hard-lock
[ ] submit timeout becomes UNCERTAIN
[ ] trade updates pass through Inbox
[ ] restart reconciles unresolved state
[ ] secrets redacted
[ ] market data feed explicit
```

---

## 251. Proposed ADRs after this document

```text
ADR - ExecutionProvider terminology
ADR - ClientOrderReference
ADR - ProviderOrderIdentity model
ADR - ExecutionCertainty and no-blind-retry
ADR - ProviderAccountIdentity
ADR - InstrumentTradingConstraints boundary
ADR - RuntimeSafetyMode vs provider environment
ADR - ExecutionProvider vs MarketDataProvider separation
ADR - ProviderSession belongs to Runtime
```

---

## 252. ADR priority

Before coding LOT-05, the minimum high-priority ADRs are :

```text
ClientOrderReference
ProviderOrderIdentity
ExecutionCertainty
RuntimeSafetyMode
```

---

## 253. Backlog additions

Candidate tasks :

```text
define ClientOrderReference
add provider order mapping contract
add provider fill identity contract
add sandbox safety mode
add provider readiness contract
add no-blind-retry tests
add provider SDK import architecture tests
```

---

## 254. Backlog tasks to defer

```text
PositionAccountingMode implementation
MarginAccountSnapshot
FinancingCharge
FIX session store
IBKR Gateway supervisor
Binance rate-limit state
cTrader OAuth runtime
```

---

## 255. Testing philosophy

Test the canonical contract with :

```text
Fake provider first
```

then provider-specific qualification.

---

## 256. Fake provider value

A Fake can deterministically simulate :

```text
accept
reject
partial fill
duplicate fill
timeout after send
stream disconnect
out-of-order events
```

---

## 257. Why Fake is not enough

Provider sandbox tests remain mandatory for :

```text
actual SDK behavior
actual IDs
actual ordering
actual reconnect
actual rate limits
```

---

## 258. Contract test layering

```text
Unit tests
    |
    v
Provider contract tests
    |
    v
Sandbox integration tests
    |
    v
Fault/recovery qualification
```

---

## 259. Property tests

Useful for :

```text
Decimal mappings
quantity constraints
idempotency
state transitions
```

---

## 260. Architecture tests

Require :

```text
no provider SDK in Domain
no ORM in Domain
no raw float economic truth
no secret literals
```

---

## 261. Provider fixture policy

Fixtures must be :

```text
sanitized
versioned
traceable to provider/schema version
```

---

## 262. Provider upgrade policy

An SDK upgrade requires :

```text
contract tests
sandbox read probe
controlled order probe if command path changed
reconnect test
```

---

## 263. Provider deprecation policy

If an SDK becomes stale :

```text
keep canonical port
replace infrastructure implementation
```

without Domain change.

---

## 264. Current SDK observations influence only Infrastructure

Examples :

```text
alpaca-py version
binance-sdk-spot version
ib_async version
ctrader-open-api version
```

are not Domain concerns.

---

## 265. Source-of-truth hierarchy

Provider implementation should prefer :

```text
official current protocol/API docs
official SDK source
sandbox behavior
```

in that order where possible.

---

## 266. Third-party repositories

Use for :

```text
examples
historical evidence
failure patterns
```

not as normative provider guarantees.

---

## 267. Security architecture

Provider integrations are privileged boundaries.

---

## 268. Least privilege

Use :

```text
read-only scope for read probes
trading scope only when required
withdrawal/funding permissions disabled where possible
```

---

## 269. Account verification

Before ready :

```text
expected account identity
```

must match.

---

## 270. Environment verification

Before ready :

```text
expected sandbox environment
```

must match.

---

## 271. Capability verification

Before submit :

```text
required trading capability
```

must be available.

---

## 272. Instrument verification

Before submit :

```text
instrument mapping
constraints
tradability
```

must be available.

---

## 273. Account-state verification

For leveraged providers later :

```text
margin/risk freshness
```

must be available.

---

## 274. Command preflight

Canonical preflight :

```text
Order valid?
Risk allows?
Provider supports?
Instrument constraints satisfied?
Runtime ready?
Account ready?
```

---

## 275. Provider final acceptance

Even after preflight :

```text
provider can reject
```

and that is normal.

---

## 276. Provider command trace

Runtime can record :

```text
provider
operation
canonical_order_id
client_reference
provider_order_id
request correlation
outcome
error code
observed_at
```

---

## 277. Command trace is not Domain Event

It is infrastructure/audit evidence.

---

## 278. Provider event trace

Similarly preserve raw event metadata where useful for incident analysis.

---

## 279. Audit objective

For every economic effect, be able to reconstruct :

```text
intent
risk decision
remote command
provider acknowledgement/fact
local mutation
```

---

## 280. Domain remains deterministic

Provider uncertainty is handled outside pure domain rules.

---

## 281. Strategy remains provider-independent

A Strategy should not know :

```text
Alpaca
Binance
IBKR
cTrader
```

unless intentionally provider-specific.

---

## 282. Risk remains mostly provider-independent

Risk can consume provider/account facts but should not depend on SDK types.

---

## 283. Portfolio remains canonical

Portfolio reflects economic state, not provider wire schemas.

---

## 284. OMS remains canonical

OMS state transitions reflect order semantics, not provider enum names.

---

## 285. Provider status mapping

Each adapter maps provider states into canonical states.

---

## 286. Unknown provider states

A provider state with no safe canonical mapping must not be silently coerced.

Use :

```text
ProviderProtocolError
or explicit extension handling
```

---

## 287. State mapping must be fixture-tested

Especially for :

```text
partial fill
pending cancel
inactive/held
expired
rejected
```

---

## 288. Account type extensions

HEDGED/NETTED is not needed for Alpaca.

Keep extension point without forcing current APIs.

---

## 289. Multi-asset extensions

IBKR demonstrates future need for richer Instrument metadata.

Do not destabilize 0.5 for unimplemented asset classes.

---

## 290. Crypto extensions

Binance demonstrates :

```text
asset pair
fee asset
24/7
```

but these are deferred until Binance implementation.

---

## 291. FX/CFD extensions

cTrader demonstrates :

```text
pip
contract size
swap
leverage
margin
hedging/netting
```

reserved for 1.2.

---

## 292. Multi-provider roadmap interpretation

```text
0.5
Alpaca PAPER vertical slice

0.6
Reconciliation & Recovery

0.7
Security & Operations

0.8
Broker/Provider Compliance + IBKR

1.1
IBKR Expansion

1.2
cTrader / FX-CFD Expansion
```

Binance can be scheduled according to product priority after canonical provider compliance foundations.

---

## 293. Provider Compliance milestone interpretation

0.8 should validate not only a broker adapter but the provider-neutral architecture itself.

---

## 294. IBKR as strong compliance provider

IBKR is a good stress test because it exercises :

```text
stateful session
multi-level identities
contract qualification
entitlements
recovery
```

---

## 295. cTrader as later domain stress test

cTrader is a strong test for :

```text
FX/CFD semantics
margin
position modes
financing
```

---

## 296. Binance as venue stress test

Binance is a strong test for :

```text
exchange filters
rate limits
24/7
asset balances
```

---

## 297. Four-provider confidence criterion

A canonical concept is strong if :

```text
it maps naturally to all four providers
without special cases in Domain
```

---

## 298. Four-provider rejection criterion

A concept should remain provider-specific if :

```text
it exists only due to one transport/provider
and has no shared economic meaning
```

---

## 299. Examples of provider-specific concepts

```text
Binance recvWindow
IBKR nextValidId
IBKR clientId
cTrader clientMsgId
cTrader symbolId
FIX MsgSeqNum
Alpaca X-Request-ID
```

---

## 300. Examples of canonical concepts

```text
Order
Fill
Balance
Position
Instrument
ClientOrderReference
ExecutionCertainty
Provider identity mappings
```

---

## 301. Examples of application/runtime shared concepts

```text
Capabilities
Constraints
ProviderAccountSnapshot
ProviderSession
ProviderEnvironment
ProviderHealth
```

---

## 302. Final layer classification table

| Concept | Domain | Application | Runtime | Persistence | Provider ACL |
|---|---:|---:|---:|---:|---:|
| Order | yes | use | store | yes | map |
| Fill | yes | use | no | yes | map |
| ClientOrderReference | execution VO | yes | use | yes | map |
| ProviderOrderIdentity | no | yes | use | yes | yes |
| ProviderFillIdentity | no | yes | use | yes | yes |
| ProviderAccountIdentity | no | yes | yes | maybe | yes |
| ExecutionCertainty | execution domain/application | yes | use | yes | map |
| InstrumentTradingConstraints | reference/application | yes | use | optional cache | extract |
| ProviderSession | no | no | yes | optional metadata | implement |
| ProviderRateLimitState | no | no | yes | no | extract |
| ProviderClockOffset | no | no | yes | no | extract |
| PositionAccountingMode | future domain | future | use | future | map |

---

## 303. `ClientOrderReference` exact placement

Recommended placement :

```text
execution bounded context Value Object
```

not global Foundation unless reused widely.

---

## 304. `ProviderOrderIdentity` exact placement

Recommended placement :

```text
execution application/provider integration contract
```

not Order Entity property unless the current aggregate design specifically benefits from it.

---

## 305. `ProviderFillIdentity` exact placement

Recommended placement :

```text
execution integration/persistence contract
```

---

## 306. `ProviderAccountIdentity` exact placement

Recommended placement :

```text
provider integration/application model
```

---

## 307. `InstrumentTradingConstraints` exact placement

Recommended placement :

```text
market/reference application model
```

with immutable snapshots.

---

## 308. `ExecutionCertainty` exact placement

Recommended placement :

```text
execution bounded context
```

because it affects order command lifecycle and recovery.

---

## 309. ProviderSession exact placement

```text
runtime/infrastructure
```

---

## 310. ProviderEnvironment exact placement

```text
runtime/configuration
```

---

## 311. RuntimeSafetyMode exact placement

```text
runtime/application configuration
```

with strong validation.

---

## 312. ProviderCapabilities exact placement

```text
application/reference boundary
```

---

## 313. Provider errors exact placement

Canonical categories :

```text
application/integration errors
```

raw SDK errors stay infrastructure.

---

## 314. Provider snapshots exact placement

```text
application DTO / integration facts
```

not Domain aggregate replacement.

---

## 315. Potential code skeleton

```text
execution/
  domain/
    order.py
    fill.py
    execution_certainty.py
    client_order_reference.py

  ports/
    execution_command.py
    execution_query.py
    execution_events.py

  integration/
    provider_order_identity.py
    provider_fill_identity.py
```

Exact topology should respect current repository organization.

---

## 316. Runtime skeleton

```text
runtime/
  safety_mode.py
  provider_environment.py
  readiness.py
```

Only introduce files when actual implementation requires them.

---

## 317. Reference-data skeleton

```text
market_data/
  constraints.py
  capabilities.py
```

or existing reference-data bounded context equivalent.

---

## 318. Persistence skeleton

```text
persistence/
  models/
    provider_order_mapping.py
    provider_fill_mapping.py
    provider_instrument_mapping.py
```

if existing broker mappings cannot cover the semantics.

---

## 319. Avoid duplicate abstractions

Before adding new classes, inspect existing :

```text
InstrumentMapping
BrokerMapping
OrderRepository
FillRepository
Portfolio repositories
```

and extend only where necessary.

---

## 320. Migration strategy

If provider mapping tables already exist :

```text
extend safely
```

rather than create parallel models.

---

## 321. Backward compatibility

0.5 pre-1.0 allows change, but public API churn should still be intentional.

---

## 322. Public API rule

Provider-specific types should not be re-exported from top-level `pytradekit`.

---

## 323. Provider plugin possibility

Future provider packages could become optional plugins.

Not required now.

---

## 324. Core package objective

A user installing core PyTradeKit should be able to run :

```text
Domain
Backtest
Fake/Paper internal runtime
```

without provider SDKs.

---

## 325. Provider extras objective

Only users of a provider pay its dependency cost.

---

## 326. Provider configuration objective

No provider config should affect another provider package.

---

## 327. Cross-provider Portfolio future

A global portfolio can aggregate :

```text
Alpaca equities
Binance assets
IBKR positions
cTrader FX/CFD exposures
```

only if provider adapter mappings remain clean.

---

## 328. Global risk future

Global Risk may eventually consume :

```text
canonical positions
balances
currency exposures
margin observations
```

without provider SDK knowledge.

---

## 329. Valuation future

Providers may not supply comparable valuation fields.

PyTradeKit valuation should use canonical prices/currencies, not provider account totals as universal truth.

---

## 330. Currency model importance

Multi-provider integration reinforces strict Currency/Money semantics.

---

## 331. Asset vs Currency distinction

Binance/cTrader can expose assets that function as quote/deposit assets.

Do not collapse every asset into fiat Currency if the current model distinguishes them.

---

## 332. Provider market data source metadata

Backtests must preserve source lineage.

---

## 333. Historical data reproducibility

Provider historical APIs should not be assumed immutable.

Persist/version datasets for reproducible backtests.

---

## 334. Runtime market data vs backtest data

The MarketDataPort can have separate runtime and research implementations.

---

## 335. Provider-specific calendar data

Can be mapped into canonical Session/Calendar concepts when required.

---

## 336. Order ownership tag

ClientOrderReference can help identify PyTradeKit-originated orders.

---

## 337. Ownership is not authorization

Even if an order lacks the tag, account exposure may still matter for Risk.

---

## 338. Reconcile foreign order policy

Future choices :

```text
IGNORE_FOR_CONTROL_BUT_OBSERVE
IMPORT_READ_ONLY
ADOPT_EXPLICITLY
```

No automatic adoption by default.

---

## 339. Manual provider operations

Provider UIs may modify state externally.

This is normal, not an impossible condition.

---

## 340. Provider supportability

Audit metadata should make provider support cases diagnosable.

---

## 341. Request/trace IDs

Provider request IDs can be captured where available.

Do not promote them into Domain IDs.

---

## 342. Health endpoint future

A runtime health endpoint can expose :

```text
provider session status
last event age
snapshot freshness
reconciliation status
```

without secrets.

---

## 343. Readiness endpoint future

Readiness should be stricter than liveness.

---

## 344. Liveness

```text
process alive
```

---

## 345. Readiness

```text
safe to accept new trading command
```

---

## 346. Circuit breaker future

Provider-specific outages may trigger a runtime circuit breaker.

Not required in 0.5 unless needed.

---

## 347. Provider throttling future

Runtime may enter :

```text
THROTTLED
```

without becoming fully unavailable.

---

## 348. Strategy behavior under provider degradation

Strategies should receive provider-neutral availability signals rather than SDK exceptions.

---

## 349. Risk behavior under stale state

Risk should fail closed for operations requiring fresh provider state.

---

## 350. Reconciliation unresolved policy

If critical unresolved orders remain :

```text
runtime should not be READY for new execution
```

until policy allows it.

---

## 351. Unknown order handling

An `UNCERTAIN` order must be visible in :

```text
status
metrics
logs
operator diagnostics
```

---

## 352. Operator action future

A manual resolve command may eventually exist.

Not required for 0.5 initial slice.

---

## 353. Provider adapter documentation standard

Each provider should document :

```text
environments
SDK/protocol version
supported asset classes
supported order types
identity mappings
retry policy
stream/event source
reconciliation strategy
rate limits
known sandbox differences
```

---

## 354. Alpaca provider manifest target

```text
provider = alpaca
environment = paper
asset_scope = us_equities
execution = Trading API
facts = TradingStream
market_data = Stock Market Data
```

---

## 355. Binance manifest future

```text
provider = binance
venue = spot
environment = demo/testnet
execution = Spot REST
facts = User Data Stream
market_data = Market Streams
```

---

## 356. IBKR manifest future

```text
provider = ibkr
environment = paper
transport = TWS
runtime = IB Gateway
execution = TWS API
facts = callbacks
```

---

## 357. cTrader manifest future

```text
provider = ctrader
broker = pepperstone
environment = demo
transport = Open API Protobuf
execution = Open API
facts = ExecutionEvent
```

---

## 358. Provider manifest is diagnostic

It is not a Domain Entity.

---

## 359. Provider implementation maturity

Each provider can advertise :

```text
EXPERIMENTAL
SANDBOX_QUALIFIED
PRODUCTION_QUALIFIED
```

later.

---

## 360. Release policy

Do not market a provider as production-ready before fault/recovery qualification.

---

## 361. Current provider maturity

At the time of this architecture document :

```text
Alpaca
    discovery complete
    implementation next

Binance
    architecture discovery only

IBKR
    architecture discovery only

cTrader/Pepperstone
    architecture discovery only
```

---

## 362. Provider comparative architecture gate

This document closes when all critical decisions are explicit enough for Alpaca LOT-05.

---

## 363. Gate checklist - identity

```text
[x] Canonical OrderId remains internal
[x] ClientOrderReference recognized
[x] ProviderOrderIdentity recognized
[x] ProviderFillIdentity recognized
[x] ProviderAccountIdentity recognized
[x] Instrument mapping scope recognized
```

---

## 364. Gate checklist - execution

```text
[x] Command/fact split
[x] Partial fills
[x] Cancel race
[x] No blind retry
[x] UNCERTAIN
[x] Reconciliation required
```

---

## 365. Gate checklist - account

```text
[x] Balance distinct from Position
[x] Account-wide observation recognized
[x] External activity recognized
[x] HEDGED/NETTED extension point recognized
```

---

## 366. Gate checklist - constraints

```text
[x] InstrumentTradingConstraints needed
[x] Capabilities separate from constraints
[x] Provider remains final authority
[x] Constraint refresh without auto-resubmit
```

---

## 367. Gate checklist - runtime

```text
[x] ProviderSession belongs Runtime
[x] Provider-specific environment retained
[x] Sandbox safety mode
[x] Readiness stronger than connected
[x] Rate/pacing runtime state
[x] clock offset runtime-only
```

---

## 368. Gate checklist - persistence

```text
[x] Provider IDs separate from canonical IDs
[x] mapping persistence required
[x] Inbox
[x] Outbox
[x] UoW
[x] no provider columns explosion
```

---

## 369. Gate checklist - provider isolation

```text
[x] SDK types blocked from Domain
[x] Transport blocked from Domain
[x] provider errors mapped
[x] provider-specific metadata retained only at boundary
```

---

## 370. Gate checklist - security

```text
[x] SecretsPort
[x] environment hard-lock
[x] expected account verification
[x] no LIVE fallback
[x] redaction
```

---

## 371. Gate result

```text
PASS FOR LOT-05 DESIGN
```

subject to implementing the identified minimum contracts.

---

## 372. Minimum contracts before Alpaca runtime coding

Recommended :

```text
1. ClientOrderReference
2. ProviderOrderIdentity contract
3. ProviderFillIdentity / external fill mapping
4. RuntimeSafetyMode or equivalent PAPER hard-lock
5. explicit ExecutionCertainty / uncertain submission representation
6. adapter architecture tests
```

---

## 373. Contracts that can wait

```text
ProviderRateLimitState generalized API
ProviderClockOffset public API
PositionAccountingMode
MarginAccountSnapshot
FinancingCharge
FIX session abstractions
```

---

## 374. Integration sequence after this document

```text
43 Comparative Architecture
        |
        v
Alpaca read-only PAPER probe
        |
        v
Alpaca controlled order probe
        |
        v
Alpaca integration contract freeze
        |
        v
LOT-05 PAPER Runtime Configuration
        |
        v
Alpaca ACL
        |
        v
Alpaca Execution
        |
        v
Snapshots / Market Data
        |
        v
Persistent PAPER Runtime
        |
        v
Qualification
```

---

## 375. Updated discovery roadmap

```text
LOT-04A
Alpaca API & SDK analysis
DONE

LOT-04B
Binance Spot architecture validation
DONE

LOT-04C
IBKR architecture validation
DONE

LOT-04D
Pepperstone + cTrader architecture validation
DONE

LOT-04E
Provider Comparative Architecture
DONE with this document

LOT-04F
Alpaca PAPER read-only probes
NEXT

LOT-04G
Alpaca controlled order probes

LOT-04H
Alpaca integration contract freeze

LOT-05
PAPER Runtime Configuration
```

---

## 376. Naming of next documents

Possible continuation :

```text
44_PYTRADEKIT_ALPACA_PAPER_PROBE_HARNESS.md
45_PYTRADEKIT_ALPACA_CONTROLLED_ORDER_PROBE.md
46_PYTRADEKIT_ALPACA_INTEGRATION_CONTRACT_FREEZE.md
```

Numbering may be adapted to repository documentation conventions.

---

## 377. Architectural north star

```text
                   CANONICAL TRADING INTENT
                             |
                             v
                      PYTRADEKIT DOMAIN
                             |
                             v
                       APPLICATION
                             |
               +-------------+-------------+
               |                           |
               v                           v
       Execution Provider          Market Data Provider
               |                           |
               v                           v
         Provider ACL                  Provider ACL
               |                           |
               v                           v
          Transport/SDK                Transport/SDK
               |                           |
               v                           v
          External system              External system
```

---

## 378. Architectural promise

PyTradeKit promises :

```text
canonical semantics
explicit uncertainty
controlled side effects
durable local state
provider isolation
reconciliation
```

It does not promise :

```text
all providers behave identically
all features are universally supported
network exactly-once execution
sandbox equals LIVE
```

---

## 379. Final principle - economic meaning

> The Domain owns economic meaning. Providers own operational reality.

---

## 380. Final principle - IDs

> Canonical IDs express PyTradeKit identity. Provider IDs express external evidence.

---

## 381. Final principle - side effects

> A remote side effect that cannot be proven must be reconciled, not retried blindly.

---

## 382. Final principle - capabilities

> Feature availability is discovered and validated, not assumed from a provider name.

---

## 383. Final principle - constraints

> Canonical constraints capture shared semantics; provider-specific rules remain authoritative.

---

## 384. Final principle - sessions

> Connection recovery is not state recovery.

---

## 385. Final principle - market data

> Market data quality, feed and entitlement are part of the observation context.

---

## 386. Final principle - account state

> PyTradeKit may own an order without owning every economic change in the account.

---

## 387. Final principle - incremental generalization

> Generalize only after at least two providers demonstrate the same economic concept.

---

## 388. Final principle - avoid speculative abstractions

> Do not add future FX, margin, FIX or gateway concepts to the 0.5 Domain when only an extension point is required.

---

## 389. Sources internes principales

```text
39_PYTRADEKIT_ALPACA_API_SDK_INTEGRATION_ANALYSIS.md
40_PYTRADEKIT_BINANCE_SPOT_API_SDK_INTEGRATION_ANALYSIS.md
41_PYTRADEKIT_IBKR_API_SDK_INTEGRATION_ANALYSIS.md
42_PYTRADEKIT_PEPPERSTONE_CTRADER_API_SDK_INTEGRATION_ANALYSIS.md
PYTRADEKIT_ROADMAP_COMPLETE.md
```

---

## 390. Source architecture summary - Alpaca

L'étude Alpaca a établi :

```text
PAPER / LIVE explicit
TradingClient commands
TradingStream facts
client_order_id
request trace
market data feed capabilities
no blind SDK retry
```

---

## 391. Source architecture summary - Binance

L'étude Binance a établi :

```text
REST + WS API + streams
newClientOrderId
UNKNOWN outcomes
exchangeInfo filters
weighted rate limits
asset balances
24/7
```

---

## 392. Source architecture summary - IBKR

L'étude IBKR a établi :

```text
Gateway/TWS session
nextValidId
clientId
orderId/permId/execId
conId
market data entitlements
stateful recovery
```

---

## 393. Source architecture summary - cTrader/Pepperstone

L'étude cTrader a établi :

```text
broker/platform separation
Open API primary integration
FIX secondary transport
clientOrderId/dealId/symbolId
HEDGED/NETTED
margin/leverage/swap
Twisted/Protobuf
```

---

## 394. Architectural maturity assessment

Before provider studies :

```text
broker-agnostic by intent
```

After provider studies :

```text
provider-agnostic by comparative evidence
```

The architecture is not complete, but it is now grounded in four materially different external systems.

---

## 395. What remains uncertain

```text
exact public class names
exact package placement
exact constraint snapshot schema
exact provider capability enum
exact fee abstraction
exact provider session API
```

These can be resolved incrementally during implementation.

---

## 396. What is no longer uncertain

```text
canonical IDs must stay internal
provider identities must be durable
blind retry is unsafe
reconciliation is mandatory
Inbox/Outbox/UoW are justified
Balance and Position are distinct
provider constraints need a boundary
runtime environment safety must be explicit
SDK types must not leak
```

---

## 397. Decision on provider comparative gate

This architecture gate is considered :

```text
CLOSED FOR 0.5
```

once the minimum contracts listed in section 372 are implemented or explicitly mapped to existing equivalents.

---

## 398. Next engineering action

Proceed to :

```text
LOT-04F - Alpaca PAPER Read-Only Probe Harness
```

using the comparative constraints defined here.

---

## 399. Probe design rule

The probe must validate actual provider behavior without adding provider semantics to the Domain.

---

## 400. Final conclusion

The four studies show that PyTradeKit is not integrating four versions of the same broker.

It is integrating four distinct distributed trading systems :

```text
Alpaca
    hosted broker API

Binance
    exchange API

IBKR
    broker + stateful gateway

Pepperstone/cTrader
    broker + trading platform + multiple transports
```

The architecture must therefore preserve two things simultaneously :

```text
shared economic meaning
```

and :

```text
provider operational truth
```

The shared economic core is now sufficiently clear to proceed :

```text
Order
Fill
Balance
Position
Instrument
Canonical IDs
ClientOrderReference
ExecutionCertainty
Provider identity mappings
Constraints
Capabilities
Reconciliation
```

The provider-specific operational layer remains responsible for :

```text
SDKs
protocols
connections
authentication
rate limits
clock skew
session IDs
provider IDs
market-data entitlements
provider-specific constraints
```

This separation is the architecture that allows PyTradeKit to implement Alpaca PAPER in 0.5 without becoming Alpaca-specific, then add IBKR, Binance and cTrader later without rewriting the core trading model.