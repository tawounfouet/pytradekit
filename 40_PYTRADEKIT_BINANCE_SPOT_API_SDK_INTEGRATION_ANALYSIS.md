# 40 - PyTradeKit - Binance Spot API & SDK Integration Analysis

**Projet :** PyTradeKit  
**Milestone de référence :** `0.5.x - Persistence + Alpaca Paper`  
**Document :** Analyse d'intégration Binance Spot API et SDK Python  
**Version :** 1.0  
**Date :** 2026-10-22  
**Statut :** Architecture validation provider - Binance Spot non ciblé pour implémentation 0.5  
**Périmètre :** Binance Spot REST API, WebSocket API, WebSocket Market Streams, User Data Stream, Demo Mode, Testnet, SDK Python officiel, règles de marché, rate limits, sécurité, idempotence, recovery et implications pour l'architecture provider-agnostic de PyTradeKit

---

## 1. Objet du document

Ce document analyse Binance Spot comme second provider de référence pour PyTradeKit.

L'objectif immédiat n'est pas d'ajouter Binance comme provider de production dans le milestone `0.5.x`.

L'objectif est de répondre à une question architecturale plus importante :

> Les abstractions canoniques de PyTradeKit, actuellement éprouvées contre Alpaca, sont-elles suffisamment générales pour représenter un exchange crypto structurellement différent sans introduire de concepts Binance dans le Domain ?

Binance est particulièrement utile pour cette validation car son modèle diffère d'Alpaca sur plusieurs axes :

```text
broker traditionnel
vs
crypto exchange

positions
vs
asset balances

asset metadata
vs
symbol filters

simple request rate limits
vs
weighted IP rate limits + order counters

private trading stream
vs
User Data Stream

PAPER
vs
Demo Mode / Testnet

market session constraints
vs
24/7 spot markets
```

Cette étude cherche donc à :

- comprendre les primitives actuelles de Binance Spot ;
- identifier les contrats provider réellement communs avec Alpaca ;
- identifier les contraintes spécifiques qui doivent rester dans l'ACL ;
- tester la pertinence des concepts `Order`, `Fill`, `Balance`, `InstrumentId`, `ExecutionCertainty`, `CapabilityProvider`, Inbox, Outbox et reconciliation ;
- préparer une architecture future Binance sans contaminer le milestone 0.5 ;
- éviter de généraliser prématurément à partir d'Alpaca seul.

---

## 2. Conclusion exécutive

L'analyse Binance confirme plusieurs choix fondamentaux déjà réalisés dans PyTradeKit.

Les concepts suivants ne sont pas des abstractions Alpaca accidentelles :

```text
canonical OrderId
provider client order reference
external order id
ExecutionCertainty
UNCERTAIN submission state
no blind retry
Inbox deduplication
Outbox
provider anti-corruption layer
command/fact separation
startup reconciliation
provider-specific capabilities
provider-specific instrument mapping
```

Binance apporte toutefois cinq contraintes supplémentaires qui renforcent ou élargissent le design.

Premièrement, Binance Spot expose directement des règles de marché dynamiques et symbol-specific via `exchangeInfo` et ses filters :

```text
PRICE_FILTER
PERCENT_PRICE
PERCENT_PRICE_BY_SIDE
LOT_SIZE
MARKET_LOT_SIZE
MIN_NOTIONAL
NOTIONAL
MAX_NUM_ORDERS
MAX_POSITION
...
```

Cela justifie un concept canonique plus riche de :

```text
InstrumentTradingConstraints
```

Deuxièmement, Binance possède un système de rate limits multidimensionnel :

```text
REQUEST_WEIGHT
RAW_REQUESTS
ORDERS
IP based limits
account unfilled order counts
Retry-After
429
418 ban
```

Cela nécessite un modèle provider/runtime plus riche qu'un simple `requests_per_minute`.

Troisièmement, les requêtes signées dépendent de :

```text
timestamp
recvWindow
signature
server time
```

Le clock skew devient donc une préoccupation explicite d'infrastructure.

Quatrièmement, Binance sépare clairement :

```text
REST API
WebSocket API
WebSocket Market Streams
User Data Stream
```

Cette séparation confirme que PyTradeKit doit maintenir des frontières techniques distinctes entre :

```text
commands
queries
private facts
market data
```

Cinquièmement, le SDK Python officiel actuel possède lui aussi un retry automatique configurable et activé par défaut :

```text
retries = 3
backoff = 1000 ms
```

Comme avec Alpaca, aucune commande économique PyTradeKit ne doit hériter aveuglément de cette policy.

Conclusion générale :

> Binance est un excellent provider de validation architecturale pour PyTradeKit, mais son implémentation doit rester hors scope du milestone 0.5. Les enseignements Binance doivent influencer les contrats canoniques avant de figer définitivement le runtime provider et l'ACL Alpaca.

---

## 3. Sources de référence

### 3.1 Documentation officielle Binance

Source principale :

```text
https://developers.binance.com
```

Pages étudiées :

```text
https://developers.binance.com/en/docs/products/spot/rest-api
https://developers.binance.com/en/docs/products/spot/web-socket-api
https://developers.binance.com/en/docs/products/spot/user-data-stream
https://developers.binance.com/en/docs/products/spot/filters
https://developers.binance.com/en/docs/products/spot/demo-mode/general-info
https://developers.binance.com/en/docs/products/spot/testnet
```

Page produit générale :

```text
https://www.binance.com/en/binance-api
```

### 3.2 SDK Python officiel

Dépôt :

```text
https://github.com/binance/binance-connector-python
```

Le dépôt est actif.

Le SDK est désormais organisé en packages distincts par produit.

Pour Spot :

```text
binance-sdk-spot
```

Version observée au 2026-10-22 dans le repository :

```text
13.2.0
```

### 3.3 Postman officiel

Dépôt :

```text
https://github.com/binance/binance-api-postman
```

Il fournit des collections et environnements Postman officiels permettant d'explorer les REST APIs.

Il est utile pour :

```text
manual API discovery
request signing understanding
endpoint verification
error reproduction
environment comparison
```

Il n'est pas une dépendance runtime.

### 3.4 Ancien client fourni par l'utilisateur

Une implémentation historique `ClientBinance` a également été analysée.

Elle utilise l'écosystème historique :

```python
from binance.client import Client
from binance import ThreadedWebsocketManager
```

Cette implémentation est précieuse comme trace d'expérience fonctionnelle, mais elle ne doit pas servir de fondation technique pour la future intégration PyTradeKit.

---

## 4. Positionnement de Binance dans PyTradeKit

Binance fournit de nombreuses familles d'API.

```text
Binance
|
+-- Spot
|
+-- Margin
|
+-- USD-M Futures
|
+-- COIN-M Futures
|
+-- Options
|
+-- Portfolio Margin
|
+-- Algo Trading
|
+-- Wallet
|
+-- Staking
|
+-- Copy Trading
|
+-- other products
```

Pour une première future intégration PyTradeKit, le scope doit être strictement :

```text
SPOT
```

Hors scope initial :

```text
Margin
Futures
Options
Portfolio Margin
Copy Trading
Algo products
Wallet operations
Deposits / withdrawals
Staking
Loans
```

Cette limitation est essentielle.

Une abstraction `BinanceAdapter` couvrant tout Binance serait beaucoup trop large et mélangerait des modèles économiques différents.

---

## 5. Pourquoi Binance est un provider de validation idéal

Alpaca et Binance partagent suffisamment de primitives pour tester les abstractions communes, mais diffèrent suffisamment pour révéler les fuites provider-specific.

### Alpaca

```text
broker account
equities
PAPER
Trading REST
TradingStream
Market Data
positions
client_order_id
```

### Binance Spot

```text
exchange account
crypto spot
Demo / Testnet
REST
WebSocket API
WebSocket Streams
User Data Stream
asset balances
symbol filters
newClientOrderId
weighted rate limits
```

Si PyTradeKit peut représenter les deux proprement, alors les abstractions de base commencent à démontrer une vraie indépendance provider.

---

## 6. SDK Python Binance actuel

### 6.1 Architecture

Le dépôt `binance-connector-python` est désormais une collection de SDK générés.

Spot fournit :

```text
REST API
WebSocket API
WebSocket Streams
```

via :

```text
binance-sdk-spot
```

### 6.2 Dépendances

Version observée :

```text
binance-sdk-spot = 13.2.0
```

Python :

```text
>=3.10,<3.15
```

Le SDK dépend notamment de :

```text
requests
urllib3
pydantic
pycryptodome
aiohttp
binance-common
```

### 6.3 Conséquence PyTradeKit

Aucune dépendance Binance ne doit devenir une dépendance core.

Future option :

```toml
[project.optional-dependencies]
binance = [
    "binance-sdk-spot==13.2.0",
]
```

Le Domain doit continuer à fonctionner sans installer cet extra.

---

## 7. Isolation SDK

Fitness function future :

```text
FF-BINANCE-001
Imports binance_sdk_spot.* and binance_common.* are forbidden outside
the Binance infrastructure adapter boundary.
```

Architecture :

```text
Domain
  |
  v
Canonical Port
  |
  v
Binance ACL
  |
  v
Binance SDK / HTTP / WebSocket
```

Jamais :

```text
Domain
  |
  v
binance_sdk_spot.*
```

---

## 8. REST API Binance Spot

La REST API couvre :

```text
market data
exchange metadata
orders
account
trades
balances
rate limits
```

Endpoint de production principal :

```text
https://api.binance.com
```

Binance expose également plusieurs endpoints alternatifs.

Les endpoints `api1` à `api4` peuvent offrir de meilleures performances mais Binance précise qu'ils peuvent être moins stables.

Cette distinction ne doit pas être propagée dans le Domain.

Elle appartient à la configuration transport.

---

## 9. WebSocket API

Binance possède une WebSocket API request-response distincte des Market Streams.

Elle permet notamment :

```text
market queries
account queries
order commands
session authentication
user data subscription
```

Le SDK Spot fournit une configuration dédiée :

```text
ConfigurationWebSocketAPI
```

avec notamment :

```text
timeout
reconnect_delay
reconnect_attempts
mode
pool_size
session_re_logon
return_rate_limits
```

Cela introduit une possibilité intéressante :

```text
REST command transport
vs
WebSocket API command transport
```

PyTradeKit ne doit cependant pas multiplier les transports avant que le besoin réel soit démontré.

Pour une première intégration future, REST reste probablement le meilleur command path de référence.

---

## 10. WebSocket Market Streams

Les Market Streams couvrent notamment :

```text
trade
aggregate trade
book ticker
partial depth
diff depth
kline
mini ticker
ticker
rolling window stats
```

Exemple :

```text
{symbol}@aggTrade
```

Les streams peuvent être :

```text
raw
combined
dynamic subscriptions
```

Architecture cible future :

```text
Binance Market Stream
        |
        v
BinanceRealtimeMarketDataAdapter
        |
        v
canonical Quote / Trade / Bar / OrderBook events
```

---

## 11. User Data Stream

Le User Data Stream est la surface privée événementielle principale.

Les événements sont poussés en temps réel.

Événements particulièrement importants :

```text
outboundAccountPosition
balanceUpdate
executionReport
```

`executionReport` représente les mises à jour d'ordre.

Architecture cible :

```text
Binance User Data Stream
        |
        v
raw executionReport
        |
        v
Inbox
        |
        v
BinanceExecutionReportMapper
        |
        v
canonical ExecutionReport / Fill
        |
        v
OMS
        |
        v
Portfolio
```

---

## 12. Command side vs Fact side

Binance confirme fortement une séparation déjà importante dans PyTradeKit.

### Command side

```text
PyTradeKit
    |
    v
ExecutionPort
    |
    v
BinanceExecutionAdapter
    |
    v
REST / WebSocket API
    |
    v
Matching Engine
```

### Fact side

```text
Matching Engine
    |
    v
User Data Stream
    |
    v
executionReport
    |
    v
Inbox
    |
    v
Canonical execution fact
```

La réponse REST à `new order` est un ACK de commande.

Elle ne doit pas être confondue avec la vérité finale de l'exécution.

---

## 13. Ordres Spot

### 13.1 Scope initial futur recommandé

```text
MARKET
LIMIT
CANCEL
QUERY ORDER
OPEN ORDERS
```

Hors premier vertical slice :

```text
STOP_LOSS
STOP_LOSS_LIMIT
TAKE_PROFIT
TAKE_PROFIT_LIMIT
OCO
OTO
OTOCO
TRAILING
PEGGED
SOR
cancelReplace
```

### 13.2 Pourquoi ce scope

Le but est de tester :

```text
submit
acknowledge
partial execution
fill
cancel
uncertain outcome
reconciliation
```

sans ajouter prématurément la complexité des ordres avancés.

---

## 14. Client order reference

Binance supporte :

```text
newClientOrderId
```

Le SDK indique qu'il s'agit d'un identifiant unique parmi les ordres ouverts.

Cette primitive est directement comparable à :

```text
Alpaca client_order_id
```

Cela justifie une abstraction provider-agnostic.

Nom conceptuel possible :

```text
ClientOrderReference
```

ou :

```text
ProviderClientOrderId
```

Relation :

```text
PyTradeKit OrderId
        |
        +-----------------------------+
        |                             |
        v                             v
provider client reference       external order id
        |                             |
        v                             v
Alpaca client_order_id          Alpaca Order.id
Binance newClientOrderId        Binance orderId
```

---

## 15. Canonical identity

PyTradeKit doit conserver ses propres identités.

```text
OrderId
FillId
InstrumentId
AccountId
```

Binance fournit ses identifiants externes.

```text
orderId
clientOrderId
tradeId
symbol
account identifiers
```

Règle :

```text
Provider identifiers correlate canonical objects.
Provider identifiers never become canonical identities.
```

---

## 16. Unknown execution outcome

C'est l'un des résultats les plus importants de l'étude.

Binance documente explicitement un timeout backend :

```text
-1007 TIMEOUT
```

avec la sémantique :

```text
send status unknown
execution status unknown
```

Binance précise que la requête peut avoir réussi dans le Matching Engine.

La recommandation officielle est :

```text
1. inspect User Data Stream
2. if status is not observed, query the API
```

Cette sémantique est quasiment une définition provider-native de :

```text
ExecutionCertainty.UNKNOWN
```

ou :

```text
OrderSubmissionState.UNCERTAIN
```

---

## 17. HTTP 5XX

Binance indique également qu'un HTTP `5XX` :

```text
must not be treated automatically as operation failure
```

L'execution status peut être inconnu et l'opération peut avoir réussi.

Cela confirme :

```text
5XX
!=
safe retry
```

Pour un ordre :

```text
POST /order
    |
    X 5XX
    |
    v
UNCERTAIN
    |
    +-- wait User Data Stream
    |
    +-- query by clientOrderId / orderId
```

---

## 18. No blind retry

Invariant PyTradeKit :

```text
One canonical submit command
must not accidentally become
two economic order submissions.
```

Flow cible :

```text
persist Order
        |
        v
persist provider client reference
        |
        v
single controlled submit
        |
        +------------------+
        |                  |
        v                  v
known response      transport uncertainty
        |                  |
        v                  v
map result            mark UNCERTAIN
                           |
                           v
              observe User Data Stream
                           |
                  +--------+--------+
                  |                 |
                  v                 v
               found            no event
                  |                 |
                  v                 v
             converge          REST query
```

---

## 19. SDK retries - point critique

Le SDK officiel Spot actuel utilise :

```text
ConfigurationRestAPI
```

avec defaults :

```text
timeout = 1000 ms
retries = 3
backoff = 1000 ms
```

C'est un point critique.

Le SDK décrit les retries comme :

```text
Number of retry attempts for failed requests
```

sans que l'abstraction utilisateur ne distingue nécessairement l'idempotence économique de chaque endpoint.

Par conséquent :

```text
ConfigurationRestAPI(retries=3)
```

ne doit jamais être accepté implicitement pour un command path PyTradeKit.

---

## 20. Safe command transport Binance

Comme pour Alpaca, plusieurs stratégies sont possibles.

### Option A - SDK avec defaults

Rejetée pour les commandes économiques.

Raison :

```text
implicit retries
```

### Option B - SDK configuré `retries=0`

Candidate forte.

Exemple conceptuel :

```python
ConfigurationRestAPI(
    ...,
    retries=0,
)
```

Cette option devra être testée contre le comportement effectif du SDK.

### Option C - transport HTTP PyTradeKit propriétaire

Possible, mais plus coûteux.

### Option D - WebSocket API command path

Possible, mais complexifie la première intégration.

### Recommandation provisoire

```text
Use official SDK
with explicit retries=0
for economic command path
```

et une policy séparée pour les reads.

Gate obligatoire :

```text
prove by test that one PyTradeKit submit causes at most one transport submit attempt
```

---

## 21. Retry policy read vs write

### Reads

Exemples :

```text
exchangeInfo
account
balances
order query
market data
server time
```

Un retry borné peut être acceptable.

### Writes

Exemples :

```text
new order
cancel
future amend
future cancelReplace
```

La policy doit être explicite.

Règle :

```text
retryable HTTP call
!=
retryable economic operation
```

---

## 22. Request security

Binance classe les endpoints par security type.

Exemples :

```text
NONE
TRADE
USER_DATA
USER_STREAM
```

Les secure endpoints sont signés.

Une API key peut être configurée avec des permissions séparées.

La documentation précise que le trading n'est pas activé par défaut sur une nouvelle API key.

Implication PyTradeKit :

```text
credentials valid
!=
trading permission available
```

Le startup doit vérifier :

```text
authentication
permissions
environment
account
capabilities
```

---

## 23. Signature

Les requêtes signées nécessitent notamment :

```text
timestamp
recvWindow
signature
```

Binance supporte actuellement plusieurs types de clés :

```text
HMAC
RSA
Ed25519
```

Le SDK gère cette complexité.

Il est préférable de conserver le mécanisme de signature dans l'ACL ou le SDK.

Le Domain ne doit jamais connaître :

```text
HMAC
RSA
Ed25519
X-MBX-APIKEY
signature
recvWindow
```

---

## 24. recvWindow

La documentation Binance impose :

```text
recvWindow <= 60000 ms
```

et recommande :

```text
5000 ms or less
```

Le server vérifie le timestamp avant et pendant le forwarding vers le Matching Engine.

Conséquence :

```text
local clock skew
network latency
recvWindow
```

peuvent provoquer un rejet avant exécution.

Cela rend le time synchronization plus important que chez Alpaca.

---

## 25. Provider clock skew

PyTradeKit doit distinguer :

```text
canonical ClockPort
```

du :

```text
Binance server time offset
```

Concept infrastructure possible :

```text
ProviderClockOffset
    provider
    local_time
    provider_time
    offset_ms
    observed_at
```

Ce n'est pas un Domain object.

Il peut servir à :

```text
signed request preparation
startup diagnostics
readiness
incident debugging
```

---

## 26. Environnements Binance

Trois environnements doivent être distingués conceptuellement :

```text
PRODUCTION
DEMO
TESTNET
```

Ils n'ont pas la même finalité.

---

## 27. Demo Mode

Demo Mode utilise des URLs dédiées.

REST :

```text
https://demo-api.binance.com/api
```

WebSocket API :

```text
wss://demo-ws-api.binance.com/ws-api/v3
```

Market Streams :

```text
wss://demo-stream.binance.com/ws
wss://demo-stream.binance.com/stream
```

La documentation demande d'utiliser l'API Spot standard avec les endpoints Demo.

Demo Mode est le candidat le plus naturel pour une future qualification comparable à Alpaca PAPER.

---

## 28. Spot Testnet

Spot Testnet constitue un environnement supplémentaire destiné au développement de l'API.

Il ne doit pas être confondu avec Demo Mode.

Future configuration conceptuelle :

```text
BinanceEnvironment
    DEMO
    TESTNET
    LIVE
```

Pour une future première implémentation :

```text
DEMO -> P0
TESTNET -> P1
LIVE -> disabled until qualification
```

---

## 29. LIVE safety

Même principe qu'Alpaca.

Une première intégration Binance doit être incapable d'atteindre LIVE par fallback.

Règle :

```text
missing environment
=> startup failure
```

Jamais :

```text
missing environment
=> production default
```

Le SDK Spot indique actuellement que l'absence de `base_path` peut conduire au endpoint de production.

Par conséquent, PyTradeKit doit toujours fournir explicitement le base path.

---

## 30. ExchangeInfo

`exchangeInfo` est une API structurante.

Elle fournit notamment :

```text
symbols
status
base asset
quote asset
precision metadata
allowed order types
filters
permissions
rate limits
```

Il ne faut pas considérer ces informations comme des constantes de code.

Elles doivent être chargées et mappées.

---

## 31. Instrument model Binance

Binance identifie les marchés par symbole :

```text
BTCUSDT
ETHUSDT
BNBUSDT
```

PyTradeKit ne doit pas utiliser le symbole Binance comme `InstrumentId` canonique.

Cible :

```text
PyTradeKit InstrumentId
        |
        v
ProviderInstrumentMapping
        |
        +-- provider = BINANCE
        +-- external_symbol = BTCUSDT
        +-- base_asset = BTC
        +-- quote_asset = USDT
```

---

## 32. Asset pair semantics

Contrairement à une equity simple, un instrument Binance Spot représente une paire.

Exemple :

```text
BTC / USDT
```

Cela force PyTradeKit à être clair sur :

```text
base asset
quote asset
trade quantity
quote notional
price denomination
```

Cette richesse ne doit pas être perdue dans un simple `symbol: str`.

---

## 33. Symbol filters

Binance expose trois catégories :

```text
symbol filters
exchange filters
asset filters
```

Ces règles sont opérationnelles et peuvent provoquer un rejet de l'ordre.

Leur représentation doit rester provider-aware à la source, puis être projetée dans un modèle canonique commun lorsque la sémantique est réellement commune.

---

## 34. PRICE_FILTER

Le filter expose :

```text
minPrice
maxPrice
tickSize
```

avec les contraintes :

```text
price >= minPrice
price <= maxPrice
price % tickSize == 0
```

Cela justifie directement :

```text
InstrumentTradingConstraints.price_increment
```

---

## 35. LOT_SIZE

Le filter `LOT_SIZE` impose notamment :

```text
minQty
maxQty
stepSize
```

Cela justifie :

```text
InstrumentTradingConstraints.quantity_increment
InstrumentTradingConstraints.min_quantity
InstrumentTradingConstraints.max_quantity
```

---

## 36. MARKET_LOT_SIZE

Le marché peut avoir des limites spécifiques pour les `MARKET` orders.

Donc :

```text
quantity constraints
```

peuvent dépendre du type d'ordre.

Le modèle canonique ne doit pas supposer une seule quantité minimale universelle.

---

## 37. MIN_NOTIONAL

`MIN_NOTIONAL` impose une valeur minimale :

```text
price * quantity >= minNotional
```

Selon la configuration, il peut s'appliquer également aux MARKET orders via une estimation basée sur un prix de référence.

Implication :

```text
order validation
```

ne peut pas toujours être réalisée à partir du prix limite seul.

---

## 38. NOTIONAL

`NOTIONAL` peut imposer :

```text
minNotional
maxNotional
```

et préciser si les limites s'appliquent aux MARKET orders.

Cela suggère :

```text
InstrumentTradingConstraints.min_notional
InstrumentTradingConstraints.max_notional
```

avec metadata de portée.

---

## 39. PERCENT_PRICE

Binance peut limiter le prix autorisé par rapport à un prix moyen ou de référence.

Ce type de règle est dynamique.

Il ne doit probablement pas être traduit en simple Value Object statique.

Approche :

```text
StaticTradingConstraints
+
DynamicProviderValidation
```

---

## 40. MAX_POSITION

Binance peut imposer une position maximale.

Cette contrainte peut ressembler à du Risk, mais elle appartient au provider/exchange.

Il faut distinguer :

```text
PyTradeKit RiskPolicy max_position
```

de :

```text
Binance exchange MAX_POSITION
```

L'ordre doit respecter les deux.

---

## 41. Modèle proposé - InstrumentTradingConstraints

Concept canonique possible :

```text
InstrumentTradingConstraints
    price_increment
    quantity_increment
    min_price
    max_price
    min_quantity
    max_quantity
    min_notional
    max_notional
    market_min_quantity
    market_max_quantity
    market_quantity_increment
    supported_order_types
    supported_time_in_force
    observed_at
```

Ne pas inclure aveuglément chaque filter Binance.

Les contraintes dynamiques ou provider-specific doivent rester dans :

```text
ProviderConstraintSet
```

---

## 42. Validation des ordres

Flow recommandé :

```text
Strategy
   |
   v
Order intent
   |
   v
Canonical validation
   |
   v
Risk
   |
   v
Provider capability validation
   |
   v
Provider constraint validation
   |
   v
submit
```

Cela évite :

```text
provider rejection as primary validation mechanism
```

tout en gardant le provider comme autorité finale.

---

## 43. Rate limits

Binance possède plusieurs dimensions :

```text
RAW_REQUESTS
REQUEST_WEIGHT
ORDERS
```

`exchangeInfo` expose les limites de l'exchange.

Chaque route possède un `weight`.

Les endpoints multi-symboles peuvent consommer davantage.

---

## 44. IP limits

Binance suit le `REQUEST_WEIGHT` par IP.

Les headers incluent :

```text
X-MBX-USED-WEIGHT-...
```

Implication :

```text
rate limit state
```

n'est pas seulement lié à une API key.

Deux runtimes sur la même IP peuvent interagir indirectement via le quota.

---

## 45. HTTP 429

Un dépassement provoque :

```text
429 Too Many Requests
```

Binance exige un backoff.

Le header :

```text
Retry-After
```

donne une indication de délai.

Le provider adapter doit respecter ce signal.

---

## 46. HTTP 418

Des violations répétées après `429` peuvent provoquer :

```text
418
```

correspondant à un ban IP temporaire.

La documentation indique une durée croissante pouvant aller de quelques minutes à plusieurs jours pour les récidives.

PyTradeKit doit considérer ce cas comme :

```text
provider degraded/unavailable
```

et non comme un simple retryable error.

---

## 47. Unfilled order count

Binance suit également les ordres non exécutés.

Headers :

```text
X-MBX-ORDER-COUNT-...
```

Le compteur est account-specific.

Il peut générer un `429`.

Cela signifie qu'un runtime de trading doit observer au moins deux familles de limites :

```text
IP request limits
account order limits
```

---

## 48. RateLimit runtime model

Concept possible :

```text
ProviderRateLimitSnapshot
    provider
    request_weight
    request_weight_limit
    order_count
    order_count_limit
    retry_after
    ip_banned
    observed_at
```

Ce modèle appartient à :

```text
runtime/infrastructure
```

pas au Domain.

---

## 49. HTTP response source semantics

Binance documente plusieurs sources de données :

```text
Matching Engine
Memory
Database
```

Elles peuvent présenter des latences différentes.

Implication importante pour reconciliation :

```text
query result absence
```

ne doit pas toujours être interprété comme une preuve immédiate que l'action n'a pas eu lieu.

La convergence doit être bornée mais tolérante à une cohérence asynchrone.

---

## 50. Order execution events

Le User Data Stream utilise :

```text
executionReport
```

pour les mises à jour d'ordre.

Cet événement contient plusieurs identifiants et états.

Il doit être mappé vers les objets canoniques existants.

---

## 51. Event identity

Le futur adapter doit identifier une clé de déduplication stable.

Candidates Binance :

```text
orderId
tradeId
execution type
event time
transaction time
clientOrderId
```

Pour un Fill, `tradeId` constitue une forte candidate d'external fill identity.

Mais la stratégie doit être validée par fixtures réelles Demo.

---

## 52. Inbox

Flow recommandé :

```text
executionReport arrives
        |
        v
derive provider event identity
        |
        v
Inbox.claim(...)
        |
        +-- duplicate -> stop
        |
        v
map event
        |
        v
OMS mutation
        |
        v
Fill if execution occurred
        |
        v
Portfolio / Balance mutation
        |
        v
Outbox
        |
        v
COMMIT
```

Cela réutilise directement le LOT-03.

---

## 53. Balances

Binance Spot représente principalement les avoirs sous forme de balances d'assets.

Exemple conceptuel :

```text
BTC
    free
    locked

USDT
    free
    locked
```

Cela diffère du modèle de position broker traditionnel.

PyTradeKit doit éviter de forcer :

```text
Balance -> Position
```

---

## 54. Position vs Balance

Chez Alpaca :

```text
position = holding in a security
cash = balance
```

Chez Binance Spot :

```text
asset balance
```

porte une part importante de l'état économique.

Donc le modèle canonique doit permettre :

```text
Balance
```

comme objet de premier rang.

Cette décision est déjà compatible avec le LOT-01/02 où les balances ont été introduites dans la persistence.

---

## 55. Locked balances

Binance distingue :

```text
free
locked
```

Une abstraction :

```text
available
total
reserved
```

peut être plus portable que les noms provider.

Exemple :

```text
total = free + locked
available = free
reserved = locked
```

Le mapping doit rester explicite.

---

## 56. Account updates

`outboundAccountPosition` est envoyé lorsqu'une balance a changé.

`balanceUpdate` couvre notamment :

```text
deposit
withdrawal
transfer
```

Cela signifie que Portfolio peut évoluer en dehors du cycle des ordres.

Future architecture :

```text
User Data Stream
    |
    +-- executionReport -> OMS / fills
    |
    +-- outboundAccountPosition -> Balance synchronization
    |
    +-- balanceUpdate -> account ledger observation
```

---

## 57. Portfolio implications

Un portfolio multi-provider ne doit pas supposer que tous les avoirs résultent d'une Position créée par Fill.

Binance Spot révèle des sources supplémentaires :

```text
deposit
withdrawal
transfer
fees
trades
```

Cela pourra motiver un futur :

```text
AccountActivity
```

ou :

```text
PortfolioLedger
```

mais ce concept ne doit pas être ajouté au 0.5 simplement parce que Binance existe.

---

## 58. Fees

Les fills Binance peuvent comporter :

```text
commission
commission asset
```

Le coût peut donc être payé dans un asset différent de l'asset quote.

Exemple :

```text
trade BTCUSDT
fee paid in BNB
```

Cela rend un simple :

```text
fee: Money(USD)
```

potentiellement insuffisant à long terme.

Le modèle futur devrait peut-être distinguer :

```text
FeeAmount
    asset
    quantity
```

de sa valorisation comptable.

---

## 59. Fractional quantities

Le crypto Spot utilise naturellement des quantités fractionnaires.

Cela valide fortement les Value Objects basés sur `Decimal`.

Le provider peut retourner les quantités et prix sous forme de chaînes décimales.

Règle :

```text
provider decimal string
        |
        v
Decimal
        |
        v
Quantity / Price / Money
```

Jamais :

```text
float
```

---

## 60. Analyse du legacy ClientBinance

L'ancien client apporte un contexte utile mais montre plusieurs patterns à ne pas reproduire.

### 60.1 SDK historique

Il utilise :

```text
python-binance style Client
ThreadedWebsocketManager
```

Le SDK officiel actuel de référence est maintenant :

```text
binance-sdk-spot
```

### 60.2 Secrets

Le client charge directement :

```text
.env
BINANCE_TESTNET_API_KEY
BINANCE_TESTNET_API_SECRET
```

PyTradeKit doit passer par :

```text
SecretsPort
```

### 60.3 Floats

Le legacy client convertit les balances en `float`.

PyTradeKit doit utiliser `Decimal`.

### 60.4 Broad exceptions

De nombreuses méthodes capturent :

```python
except Exception
```

puis retournent :

```text
None
```

Cela détruit l'information sur :

```text
rejection
rate limit
network error
unknown outcome
authentication
provider failure
```

### 60.5 Monolithic client

Le client historique agrège :

```text
account
orders
market data
order book
historical trades
advanced orders
websockets
```

dans une seule classe.

Le futur PyTradeKit doit préférer des adapters spécialisés.

---

## 61. Architecture Binance future

Proposition :

```text
src/pytradekit/providers/binance/
|
+-- config.py
|
+-- execution.py
|
+-- snapshots.py
|
+-- capabilities.py
|
+-- constraints.py
|
+-- errors.py
|
+-- rate_limits.py
|
+-- clock_sync.py
|
+-- user_data_stream.py
|
+-- market_data/
|   +-- rest.py
|   +-- streams.py
|
+-- mappers/
    +-- order.py
    +-- execution.py
    +-- balance.py
    +-- instrument.py
    +-- constraints.py
    +-- market_data.py
```

Le package final devra suivre la topologie réelle choisie pour les adapters Alpaca.

---

## 62. Adapters spécialisés

### Execution

```text
BinanceSpotExecutionAdapter
```

Responsabilités :

```text
submit market
submit limit
cancel
query order
```

### Private events

```text
BinanceUserDataReceiver
```

Responsabilités :

```text
subscribe
receive
normalize transport
deliver to Inbox
```

### Snapshots

```text
BinanceSpotSnapshotAdapter
```

Responsabilités :

```text
account
balances
open orders
recent orders
recent trades
```

### Market Data

```text
BinanceSpotHistoricalMarketDataAdapter
BinanceSpotRealtimeMarketDataAdapter
```

### Constraints

```text
BinanceSpotConstraintProvider
```

### Capabilities

```text
BinanceSpotCapabilityProvider
```

---

## 63. Environment configuration

Concept possible :

```text
BinanceSpotConfig
    environment
    rest_base_url
    websocket_api_url
    market_stream_url
    api_key_ref
    api_secret_ref
    recv_window_ms
    command_timeout_ms
    query_timeout_ms
    command_retries
    read_retries
```

Invariant :

```text
command_retries = 0
```

pour le premier vertical slice.

---

## 64. SecretsPort

Config :

```text
secret://binance/demo/api_key
secret://binance/demo/api_secret
```

Jamais :

```text
raw API key in YAML
raw secret in logs
```

---

## 65. API key safety

Le dépôt Postman Binance recommande explicitement de :

```text
not enable withdrawal permission
```

sur les clés utilisées pour les tests.

PyTradeKit devrait imposer une documentation de sécurité :

```text
TRADE only if required
USER_DATA as required
withdrawal disabled
IP restrictions recommended
separate Demo/Testnet keys
```

---

## 66. Capability model

Future capabilities :

```text
SPOT_MARKET_ORDER
SPOT_LIMIT_ORDER
SPOT_CANCEL
ORDER_QUERY
BALANCE_QUERY
REALTIME_PRIVATE_EVENTS
REALTIME_TRADES
REALTIME_BOOK
REALTIME_BARS
HISTORICAL_BARS
EXCHANGE_CONSTRAINTS
```

Contexte :

```text
provider = BINANCE
venue = SPOT
environment = DEMO
base_asset = BTC
quote_asset = USDT
```

---

## 67. Capabilities vs constraints

Important :

```text
Capability
```

répond à :

```text
Can this provider do this kind of operation?
```

Une :

```text
Constraint
```

répond à :

```text
Under which numeric and contextual conditions is it valid?
```

Exemple :

```text
LIMIT_ORDER capability = yes

but:

price tick size
min qty
min notional
max position
```

doivent encore être respectés.

---

## 68. RateLimit capability

Un simple booléen :

```text
supports_rate_limits = true
```

n'apporte rien.

Il faut plutôt exposer un snapshot provider :

```text
RateLimitSnapshot
```

et laisser le runtime décider :

```text
READY
DEGRADED
THROTTLED
BANNED
```

---

## 69. Readiness Binance

Future readiness possible :

```text
credentials resolvable
environment explicitly non-LIVE
REST reachable
server time reachable
clock offset acceptable
account authenticated
required permissions available
exchangeInfo loaded
constraints loaded
rate limits known
User Data Stream connected
startup snapshot loaded
reconciliation completed
```

---

## 70. Startup sequence future

```text
01 load profile
02 require DEMO or TESTNET
03 resolve secrets
04 initialize database
05 verify migrations
06 initialize REST read transport
07 initialize safe command transport with retries=0
08 query server time
09 calculate provider time offset
10 authenticate account
11 load exchangeInfo
12 build instrument constraints
13 load rate limits
14 load balances
15 load unresolved local orders
16 query provider orders
17 reconcile
18 connect User Data Stream
19 connect required Market Streams
20 expose READY
```

---

## 71. Reconciliation

Unresolved states :

```text
SUBMITTED without external id
UNCERTAIN
CANCEL_REQUESTED
PARTIALLY_FILLED with stream gap
```

Flow :

```text
load local order
      |
      v
provider client reference available?
      |
      v
query Binance
      |
      +-- found -> map and converge
      |
      +-- not found -> remain unresolved / bounded retry
```

Ne jamais faire :

```text
not found
=> blind resubmit
```

---

## 72. User Data Stream disconnect

Une reconnexion technique ne garantit pas que tous les événements manqués seront rejoués.

Règle provider-agnostic :

```text
stream reconnect
!=
state reconciliation
```

Après une interruption significative :

```text
reconnect
   |
   v
snapshot
   |
   v
reconciliation
```

---

## 73. WebSocket reconnect config

Le SDK officiel expose des paramètres :

```text
reconnect_delay
reconnect_attempts
```

avec un nombre de tentatives borné.

Cela est utile pour la connectivité, mais ne constitue pas une recovery policy métier.

---

## 74. Market Data

Future première surface :

```text
ticker price
trades
klines
book ticker
depth
```

PyTradeKit doit mapper vers ses types canoniques :

```text
Quote
Trade
Bar
OrderBookSnapshot
```

uniquement si ces objets font partie de la roadmap canonique.

Ne pas exposer les payloads Binance publiquement.

---

## 75. Order book

Binance rend particulièrement intéressant un futur modèle de carnet.

Mais PyTradeKit 0.5 n'en a pas besoin.

Ne pas ajouter :

```text
OrderBook
DepthUpdate
SequenceNumber
```

au core 0.5 uniquement pour Binance.

Ce sera une extension future.

---

## 76. Klines

Les klines Binance sont des chandeliers provider.

Mapping :

```text
open time
close time
open
high
low
close
volume
trade count
```

Le modèle canonique `Bar` doit définir précisément :

```text
timestamp semantics
interval semantics
closed vs in-progress bar
```

avant intégration.

---

## 77. 24/7 market

Binance Spot fonctionne différemment des marchés actions.

Il n'y a pas de notion NYSE-like de :

```text
market open
market close
trading session day
```

pour le Spot crypto standard.

Cela teste très bien les abstractions temporelles PyTradeKit.

Le Domain ne doit pas supposer :

```text
every tradable instrument has an exchange session calendar
```

---

## 78. Strategy implications

Une stratégie broker-agnostic doit pouvoir fonctionner avec :

```text
session-based market
```

ou :

```text
continuous market
```

La notion de session doit donc être capability-driven.

---

## 79. Instrument status

Binance expose un status de symbole et les capacités de trading.

Ces données doivent alimenter :

```text
ProviderInstrumentSnapshot
```

et non muter implicitement un Instrument canonique sans contrôle.

---

## 80. Error taxonomy

Le SDK actuel expose des catégories d'erreur plus riches :

```text
ClientError
RequiredError
UnauthorizedError
ForbiddenError
TooManyRequestsError
RateLimitBanError
ServerError
NetworkError
NotFoundError
BadRequestError
```

PyTradeKit doit mapper vers sa taxonomie canonique.

---

## 81. Error mapping proposé

Concept :

```text
Binance error
        |
        v
BinanceErrorMapper
        |
        +-- AuthenticationError
        +-- AuthorizationError
        +-- RateLimited
        +-- ProviderBanned
        +-- InvalidOrder
        +-- BrokerRejectedOrder
        +-- ProviderUnavailable
        +-- ProviderProtocolError
        +-- UnknownSubmissionOutcome
```

---

## 82. 4XX semantics

Un `4XX` est généralement client-side, mais il faut mapper finement :

```text
400 -> bad request / business rejection
401 -> auth
403 -> WAF/security
409 -> partial cancelReplace semantics
418 -> IP ban
429 -> rate limited
```

Ne pas faire :

```text
if 4xx:
    RejectedOrder
```

---

## 83. WAF

Binance peut retourner `403` pour certaines violations WAF ou security blocks.

Ce n'est pas équivalent à :

```text
order rejected by matching engine
```

Le mapping doit conserver la nature infrastructure/security.

---

## 84. Cancel semantics

Une demande de cancel est une commande.

Elle doit être distinguée de la confirmation finale :

```text
CANCEL_REQUESTED
```

puis événement provider / query :

```text
CANCELED
```

Une race reste possible :

```text
cancel command
     |
     +---------+
     |         |
     v         v
cancel      fill
```

Le modèle OMS 0.2 est déjà conçu pour cette race.

---

## 85. Partial fills

Binance Spot supporte naturellement des executions partielles.

Cela constitue une deuxième validation de :

```text
PARTIALLY_FILLED
Fill collection
cumulative filled quantity
```

dans le modèle PyTradeKit.

---

## 86. Fill identity

Future mapping probable :

```text
Binance tradeId
        |
        v
external_fill_id
```

avec :

```text
provider = BINANCE
symbol
orderId
tradeId
```

La clé finale doit être validée par des fixtures Demo réelles.

---

## 87. Commission

Chaque Fill doit pouvoir représenter :

```text
commission quantity
commission asset
```

Cela pourrait nécessiter à terme une évolution du modèle de fee.

Cette évolution n'est pas nécessaire pour 0.5 Alpaca tant que la spec actuelle couvre son besoin.

---

## 88. Precision

Le provider expose des precisions et filters.

Il est dangereux de faire :

```text
round(price, N)
```

à partir d'une precision nominale uniquement.

La vraie règle doit suivre :

```text
tickSize
stepSize
```

Cela justifie des helpers provider constraint-aware.

---

## 89. Avoid auto-rounding

PyTradeKit ne devrait pas silencieusement transformer :

```text
invalid requested price
```

en :

```text
nearest valid Binance price
```

sans policy explicite.

Deux choix :

```text
reject
```

ou :

```text
quantize under explicit policy
```

La stratégie doit être visible pour le caller.

---

## 90. Data freshness

Comme avec Alpaca, toute observation market data doit porter :

```text
provider timestamp
received_at
observed_at
```

et si nécessaire :

```text
sequence / update id
```

La fraîcheur doit être vérifiable.

---

## 91. Decimal policy

Tous les champs économiques :

```text
price
quantity
quote quantity
commission
balances
notional
```

doivent être convertis via `Decimal`.

Fitness function possible :

```text
no float in provider economic mappers
```

---

## 92. Audit du ClientBinance historique - place_order

Le legacy wrapper :

```text
construct params
call client.create_order
catch Exception
return None
```

ne permet pas de distinguer :

```text
known rejection
unknown submission
network failure
auth failure
rate limiting
```

Dans PyTradeKit, cette logique doit être remplacée par un résultat ou une exception typée.

---

## 93. Audit du ClientBinance historique - balances

Le legacy wrapper retourne uniquement les balances positives et ne conserve que :

```text
free
```

Cela perd :

```text
locked
zero balances if relevant
account-level metadata
```

Le futur snapshot doit préserver suffisamment d'information pour reconciliation.

---

## 94. Audit du ClientBinance historique - WebSocket

Le legacy wrapper utilise un `ThreadedWebsocketManager` unique pour :

```text
kline
ticker
depth
```

Le futur design doit distinguer :

```text
market streams
private account stream
```

car leurs garanties et responsabilités ne sont pas les mêmes.

---

## 95. Audit du ClientBinance historique - credentials

Le legacy wrapper accepte :

```text
constructor credentials
or environment variables
```

Le futur runtime doit imposer :

```text
secret references
```

et empêcher tout dump accidentel.

---

## 96. Security redaction

Tests requis :

```text
API key absent from logs
secret absent from logs
signature absent from logs if sensitive
full signed URL not logged
Authorization-like material redacted
config repr safe
exceptions sanitized
```

Le SDK `binance_common` possède déjà un concept `RedactedRepr`, mais PyTradeKit doit tester ses propres surfaces.

---

## 97. Postman repository usage

Le dépôt Postman est utile pour LOT Discovery.

Usages :

```text
manual endpoint validation
signed request inspection
Demo/Testnet endpoint validation
error code reproduction
filter inspection
order lifecycle observation
```

Il ne doit pas définir l'architecture.

---

## 98. Demo probe harness future

Si Binance devient un provider implémenté, commencer par un probe read-only.

```text
01 authenticate Demo
02 query server time
03 query exchangeInfo
04 query one symbol
05 inspect filters
06 query account
07 query balances
08 query open orders
09 subscribe User Data Stream
10 subscribe market ticker
11 capture rate limit metadata
```

Pas d'ordre au premier probe.

---

## 99. Controlled order probe

Deuxième phase seulement :

```text
01 generate canonical OrderId
02 persist newClientOrderId
03 MARKET tiny order
04 observe REST response
05 observe executionReport
06 query order
07 LIMIT away from market
08 cancel LIMIT
09 observe cancel event
10 capture rate limit headers
11 simulate transport timeout
12 validate UNCERTAIN recovery
```

---

## 100. Fixtures Binance

Future structure :

```text
tests/fixtures/binance/
|
+-- exchange_info_btcusdt.json
+-- account.json
+-- balances.json
+-- new_order_ack.json
+-- execution_report_new.json
+-- execution_report_trade.json
+-- execution_report_partial_fill.json
+-- execution_report_canceled.json
+-- order_query.json
+-- rate_limit_headers.json
+-- ticker.json
+-- kline.json
```

Toutes les fixtures doivent être sanitizées.

---

## 101. Provider comparative implications

L'étude Binance permet de requalifier certains concepts PyTradeKit.

### Confirmé comme provider-agnostic

```text
OrderId
client order reference
external order id
ExecutionCertainty
UNCERTAIN
no blind retry
Fill
Inbox
Outbox
UnitOfWork
reconciliation
provider adapters
Capabilities
SecretsPort
```

### À enrichir potentiellement

```text
InstrumentTradingConstraints
RateLimitSnapshot
ProviderClockOffset
Balance semantics
Fee representation
continuous market capability
```

---

## 102. Alpaca vs Binance - client order reference

```text
Alpaca
client_order_id

Binance
newClientOrderId
```

Conclusion :

```text
canonical provider client order reference
```

est justifiée.

---

## 103. Alpaca vs Binance - unknown submit

```text
Alpaca
network / provider uncertainty

Binance
-1007 TIMEOUT
HTTP 5XX execution status UNKNOWN
```

Conclusion :

```text
ExecutionCertainty
```

est pleinement justifiée.

---

## 104. Alpaca vs Binance - private events

```text
Alpaca
TradingStream
trade_updates

Binance
User Data Stream
executionReport
```

Conclusion :

```text
ExecutionEventReceiver
```

ou équivalent peut être provider-agnostic.

---

## 105. Alpaca vs Binance - holdings

```text
Alpaca
cash + positions

Binance Spot
asset balances
```

Conclusion :

```text
Balance
```

doit rester une primitive indépendante de `Position`.

---

## 106. Alpaca vs Binance - instrument constraints

```text
Alpaca
provider asset/order capabilities

Binance
exchangeInfo filters
```

Conclusion :

```text
InstrumentTradingConstraints
```

mérite probablement un contrat canonique.

---

## 107. Alpaca vs Binance - rate limits

```text
Alpaca
provider API limits

Binance
weighted IP limits
account order counts
429 / 418
```

Conclusion :

```text
RateLimitSnapshot
```

ne doit pas être réduit à `requests_per_minute`.

---

## 108. Alpaca vs Binance - environment

```text
Alpaca
PAPER / LIVE

Binance
DEMO / TESTNET / LIVE
```

Conclusion :

éviter un enum global trop simpliste :

```text
TradingMode.PAPER
```

si celui-ci est supposé représenter tous les providers.

Préférer :

```text
RuntimeSafetyMode
```

ou :

```text
provider-specific Environment
```

dans l'infrastructure.

---

## 109. Runtime mode design implication

Possibilité :

```text
ExecutionSafetyMode
    SIMULATED
    SANDBOX
    LIVE
```

et :

```text
ProviderEnvironment
    AlpacaPaper
    AlpacaLive
    BinanceDemo
    BinanceTestnet
    BinanceLive
```

Le premier exprime l'intention de sécurité.

Le second exprime le provider concret.

À étudier avant LOT-05.

---

## 110. Broker vs Venue terminology

Binance révèle aussi une limite de vocabulaire.

`BrokerAdapter` est naturel pour Alpaca.

Binance est plutôt une venue/exchange.

Le package générique pourrait être nommé :

```text
providers
execution_venues
trading_providers
```

plutôt que :

```text
brokers
```

Décision à prendre dans le document comparatif 41.

---

## 111. Provider-neutral terminology candidate

```text
TradingProvider
ExecutionProvider
ExecutionVenue
ProviderAdapter
```

`ExecutionProvider` semble plus général que `Broker`.

Mais aucun renommage ne doit être effectué sans analyse de l'impact sur le public API.

---

## 112. Capability context

Proposition :

```text
CapabilityContext
    provider
    environment
    venue
    asset_class
    instrument
    order_type
```

Cela permet de répondre correctement à :

```text
Can MARKET order be submitted for BTCUSDT on Binance Demo?
```

sans hardcoder Binance dans le Domain.

---

## 113. Constraint refresh

Les filters provider peuvent changer.

Ils doivent donc être traités comme :

```text
observations
```

avec :

```text
observed_at
source
version/hash
```

et non comme des constantes éternelles.

---

## 114. Runtime caching

`exchangeInfo` peut être coûteux en weight.

Le runtime doit probablement :

```text
load once at startup
cache
refresh periodically or on rejection
```

La fréquence doit être contrôlée.

---

## 115. Dynamic provider rejection

Même avec validation locale, Binance reste autorité finale.

Pattern :

```text
local validation passes
        |
        v
provider rejects due to changed constraint
        |
        v
map rejection
        |
        v
refresh constraints
        |
        v
do not auto-resubmit
```

---

## 116. Observability

Métriques candidates :

```text
binance_requests_total
binance_request_errors_total
binance_request_weight
binance_order_count
binance_rate_limited_total
binance_ip_ban_total

binance_submit_total
binance_submit_uncertain_total
binance_cancel_total

binance_user_stream_connected
binance_user_stream_reconnect_total
binance_execution_reports_total

binance_clock_offset_ms
binance_constraint_refresh_total
binance_reconciliation_unresolved_total
```

---

## 117. Structured logs

Champs :

```text
provider
environment
operation
canonical_order_id
provider_client_order_id
external_order_id
symbol
request_weight
order_count
correlation_id
status
duration_ms
```

Ne jamais logger :

```text
api_secret
signature
private key
full signed request
```

---

## 118. Provider health states

Candidat :

```text
READY
DEGRADED
THROTTLED
DISCONNECTED
AUTH_FAILED
BANNED
RECONCILING
```

Ces states appartiennent au runtime.

Ils ne doivent pas devenir les states d'un Order.

---

## 119. Demo vs real market equivalence

Même un environnement Demo ne doit jamais être traité comme preuve automatique de comportement LIVE complet.

Qualification :

```text
Demo API integration qualified
!=
production trading qualified
```

Même principe qu'Alpaca PAPER.

---

## 120. Future compliance level

Si Binance est implémenté ultérieurement :

```text
C1
unit + contract

C2
Demo integration

C3
fault/restart/reconciliation evidence

LIVE
separate explicit qualification
```

---

## 121. Scope exclusion 0.5

Aucune des choses suivantes ne doit être ajoutée au milestone 0.5 uniquement pour Binance :

```text
Binance dependency
Binance runtime
Binance credentials
Binance Demo E2E
Order book core
crypto fee ledger
Futures
Margin
Options
```

Le 0.5 reste :

```text
Alpaca PAPER implementation target
```

Binance est :

```text
architecture validation target
```

---

## 122. Impact immédiat sur LOT-04 Alpaca Discovery

Binance doit être utilisé comme contre-exemple pendant la conception.

Avant de figer un nouveau contrat, poser :

```text
Does this still make sense for Binance Spot?
```

Exemples :

```text
BrokerPositionPort?
BalancePort?
TradingMode?
ClientOrderReference?
MarketDataCapability?
InstrumentConstraints?
```

---

## 123. Nouveau gate architectural avant LOT-05

Avant de figer `PAPER Runtime Configuration`, valider :

```text
[ ] environment model does not assume Alpaca-only PAPER/LIVE
[ ] client order reference is provider-neutral
[ ] ExecutionCertainty supports Binance unknown outcomes
[ ] Balance remains independent from Position
[ ] provider constraints have an extension point
[ ] rate limits are not hardcoded as one scalar
[ ] SDK retry behavior can be overridden per command path
[ ] provider naming does not force broker-only semantics
```

---

## 124. Questions ouvertes Binance

À résoudre avant toute implémentation réelle :

1. Quels status et execution types exacts apparaissent pour MARKET, LIMIT, PARTIAL, CANCEL en Demo ?
2. Quel comportement exact Binance applique-t-il à un deuxième `newClientOrderId` identique après un timeout ?
3. `query order` par `origClientOrderId` est-il suffisamment rapide pour recovery immédiate ?
4. Quel délai moyen existe entre REST ACK et `executionReport` ?
5. Que se passe-t-il lors d'une coupure User Data Stream ?
6. Quels événements sont manqués ou rejoués après reconnect ?
7. Quel identifiant doit servir de clé Inbox pour un `executionReport` non-fill ?
8. Quel identifiant doit servir d'external Fill ID ?
9. Comment les commissions apparaissent-elles en Demo ?
10. Quels filters doivent être projetés dans le canonical constraint model ?
11. Quel cache TTL raisonnable utiliser pour `exchangeInfo` ?
12. Le SDK avec `retries=0` effectue-t-il réellement une seule tentative réseau ?
13. Quels errors SDK représentent précisément un timeout client vs `-1007` serveur ?
14. Comment capturer proprement les response headers de rate limits via le SDK ?
15. Comment synchroniser le clock sans créer une dépendance forte au provider time ?
16. Demo et Testnet exposent-ils exactement les mêmes schemas que production pour notre scope ?
17. Quelle limite maximale de connexions / subscriptions s'applique au User Data Stream ?
18. Quelle stratégie de reconnexion évite les duplications de subscriptions ?
19. Comment gérer les non-ASCII symbols récemment supportés par l'API ?
20. Quel provider environment doit être utilisé dans les tests CI opt-in ?

---

## 125. Analyse critique - SDK retries

Le fait que les SDK Alpaca et Binance proposent tous deux des retries automatiques est un signal architectural important.

PyTradeKit doit considérer les retries comme une responsabilité :

```text
operation-aware
```

et non :

```text
HTTP-client-wide
```

Classification possible :

```text
SAFE_TO_RETRY
READ_ONLY_RETRYABLE
ECONOMICALLY_UNSAFE
UNKNOWN_OUTCOME_RECONCILE
```

Exemple :

```text
GET exchangeInfo
-> READ_ONLY_RETRYABLE

GET order
-> READ_ONLY_RETRYABLE

POST new order
-> ECONOMICALLY_UNSAFE

timeout after POST new order
-> UNKNOWN_OUTCOME_RECONCILE
```

---

## 126. Potential shared contract - CommandRetryPolicy

Future infrastructure concept :

```text
CommandRetryPolicy
    operation
    max_transport_attempts
    on_timeout
    on_429
    on_5xx
```

Pour submit :

```text
max_transport_attempts = 1
on_timeout = UNCERTAIN
on_5xx = UNCERTAIN
```

Pas besoin d'en faire un Domain object.

---

## 127. Provider command trace

Comme Alpaca avec `X-Request-ID`, Binance apporte ses propres metadata.

Proposition générique :

```text
ProviderCommandTrace
    provider
    operation
    correlation_id
    canonical_order_id
    provider_client_order_id
    external_order_id
    http_status
    provider_error_code
    request_weight
    occurred_at
    outcome
```

---

## 128. Account snapshot canonicalization

Binance futur :

```text
TradingAccountSnapshot
    provider_account_reference
    balances[]
    can_trade
    permissions
    observed_at
```

Le snapshot ne doit pas inventer :

```text
portfolio_value
```

si le provider ne fournit pas une valeur équivalente.

---

## 129. Valuation

Pour construire une valeur de portfolio Spot :

```text
balances
+
market prices
+
valuation currency
```

sont nécessaires.

Ce calcul appartient au Portfolio / valuation layer, pas au mapping brut Binance.

---

## 130. Quote currency

Un portfolio crypto peut contenir :

```text
BTC
ETH
USDT
BNB
EUR
```

Il faut donc une currency/asset de valorisation explicite.

Éviter :

```text
USD assumed everywhere
```

---

## 131. Crypto asset type

PyTradeKit doit vérifier que son modèle `Instrument` et ses Value Objects représentent correctement :

```text
crypto asset
spot pair
quote currency
```

sans introduire une logique equities-only.

---

## 132. Market sessions revisit

Binance Spot peut fonctionner 24/7.

Un runtime ne doit donc pas avoir un global :

```text
if market closed:
    stop
```

sans capability provider/instrument.

---

## 133. Data stream topology

Possible future composition :

```text
BinanceMarketDataRuntime
|
+-- trade stream
+-- kline stream
+-- book ticker stream
```

La souscription doit être pilotée par les besoins de stratégie.

Ne pas subscribe `*` par défaut.

---

## 134. Backpressure

Les market streams crypto peuvent générer beaucoup d'événements.

Un futur adapter devra définir :

```text
queue bounds
drop policy
backpressure
consumer lag metrics
```

Ce problème est plus visible avec Binance qu'Alpaca.

---

## 135. Ordering and sequence

Pour le depth stream, Binance expose des update IDs et impose une procédure de reconstruction correcte du carnet.

Cette complexité est hors première intégration.

Si OrderBook est ajouté plus tard :

```text
snapshot
+
diff stream
+
sequence reconciliation
```

devra être implémenté correctement.

---

## 136. No premature OrderBook

Décision :

```text
Do not add OrderBook core abstractions
only because Binance supports depth streams.
```

Le besoin doit venir d'une roadmap fonctionnelle.

---

## 137. Symbol normalization

Binance utilise des symboles concaténés :

```text
BTCUSDT
```

Le Domain doit conserver :

```text
base asset
quote asset
canonical instrument
```

pour éviter de parser naïvement la string provider.

---

## 138. ProviderInstrumentMapping

Proposition :

```text
ProviderInstrumentMapping
    provider
    instrument_id
    external_symbol
    external_asset_id optional
    metadata
    valid_from
    valid_to
```

Cela fonctionne également pour Alpaca.

---

## 139. Capability refresh

Au startup :

```text
exchangeInfo
```

peut fournir :

```text
tradability
order types
constraints
```

Les capabilities doivent être reconstruites depuis ces facts.

---

## 140. Fail closed

Si un symbol mapping ou constraint set est absent :

```text
reject submit locally
```

plutôt que :

```text
guess provider behavior
```

---

## 141. Environment-specific constraints

Demo, Testnet et Live peuvent diverger.

Ne pas partager aveuglément un cache `exchangeInfo` entre environnements.

Key :

```text
provider
environment
symbol
```

---

## 142. Persistence implications

LOT-01 à LOT-03 semblent adaptés.

Repositories existants :

```text
orders
fills
balances
positions
processed fills
outbox
inbox
```

Binance valide particulièrement la présence de :

```text
balances
processed fill identities
inbox
```

---

## 143. Potential future persistence additions

Pas pour 0.5, mais Binance pourrait motiver :

```text
provider instrument constraints table
provider rate limit snapshots
provider account activity log
provider command traces
```

Ces objets doivent rester infrastructure.

---

## 144. UnitOfWork use

Un `executionReport` Fill peut nécessiter une transaction atomique :

```text
Inbox claim
+
Order update
+
Fill insert
+
Balance update
+
Outbox events
```

Cela confirme le design LOT-03.

---

## 145. Exactly-once economic effect

Le réseau ne garantit pas exactly-once delivery.

PyTradeKit cherche plutôt :

```text
at-least-once reception
+
idempotent processing
=
one local economic effect
```

Binance est un excellent cas de validation.

---

## 146. Cancel-fill race

Binance peut naturellement produire :

```text
cancel request
then fill
```

ou :

```text
partial fill
then cancel
```

L'OMS doit accepter les facts provider selon les transitions valides.

---

## 147. Unknown after cancellation

Une erreur réseau sur cancel ne signifie pas nécessairement :

```text
cancel failed
```

La même logique de certainty peut s'appliquer :

```text
cancel outcome uncertain
```

Cette dimension devra être étudiée dans une version ultérieure de l'OMS si elle n'est pas déjà modélisée.

---

## 148. Provider side validation

Les filters évoluent.

Même si PyTradeKit valide localement :

```text
provider remains final authority
```

Les rejections doivent être conservées avec metadata.

---

## 149. Risk vs exchange rules

Ordre de décision :

```text
canonical validity
        |
        v
risk policy
        |
        v
provider constraints
        |
        v
provider final acceptance
```

Aucune couche ne remplace les autres.

---

## 150. Recommended provider abstraction test

Créer ultérieurement une suite de contract tests conceptuels :

```text
ExecutionProviderContract
MarketDataProviderContract
AccountSnapshotProviderContract
InstrumentConstraintProviderContract
```

Puis exécuter contre :

```text
Fake provider
Alpaca
Binance
```

Le contrat ne doit contenir que les comportements réellement communs.

---

## 151. Avoid lowest-common-denominator design

Un risque inverse existe :

```text
make everything so generic
that useful provider features disappear
```

La solution :

```text
canonical common core
+
provider extension metadata
+
capabilities
```

et non :

```text
one giant universal interface
```

---

## 152. Provider extensions

Concept possible :

```text
ProviderMetadata
```

opaque pour le Domain principal mais disponible pour diagnostics.

Éviter les dicts arbitraires dans le Domain.

Les extensions doivent rester à l'application/infrastructure boundary.

---

## 153. Potential package naming issue

Si le package actuel est nommé :

```text
brokers
```

Binance montre que ce terme pourrait être trop étroit.

À étudier :

```text
providers
execution
venues
integrations
```

Aucun renommage immédiat recommandé.

---

## 154. Milestone strategy

Roadmap inchangée pour l'implémentation :

```text
0.5
Alpaca PAPER

future
Binance Spot Demo
```

Mais la phase Discovery devient :

```text
Provider Discovery
|
+-- Alpaca implementation target
|
+-- Binance architecture validation target
```

---

## 155. Documents associés

```text
39_PYTRADEKIT_ALPACA_API_SDK_INTEGRATION_ANALYSIS.md

40_PYTRADEKIT_BINANCE_SPOT_API_SDK_INTEGRATION_ANALYSIS.md

41_PYTRADEKIT_BROKER_PROVIDER_COMPARATIVE_ARCHITECTURE.md
```

Le document 41 devient fortement recommandé.

---

## 156. Objectif du document comparatif 41

Répondre à :

> Quels concepts doivent réellement appartenir au noyau provider-agnostic de PyTradeKit après confrontation d'Alpaca et Binance ?

Axes :

```text
identity
order submission
certainty
fills
balances
positions
constraints
capabilities
rate limits
market data
private streams
environments
secrets
retries
reconciliation
```

---

## 157. Tableau de correspondance initial

| Concept PyTradeKit | Alpaca | Binance Spot |
|---|---|---|
| Client order reference | `client_order_id` | `newClientOrderId` |
| External order ID | Order UUID | `orderId` |
| Private execution stream | `trade_updates` | `executionReport` |
| Holdings | Positions + cash | Asset balances |
| Market metadata | Assets/capabilities | `exchangeInfo` |
| Price increment | Provider rules | `PRICE_FILTER.tickSize` |
| Quantity increment | Provider rules | `LOT_SIZE.stepSize` |
| Minimum notional | Provider constraint | `MIN_NOTIONAL` |
| Unknown submit | network uncertainty | `-1007`, `5XX` |
| Sandbox | PAPER | Demo / Testnet |
| Rate limiting | API limits | weighted IP + order count |
| Market stream | StockDataStream | WebSocket Market Streams |
| Private stream | TradingStream | User Data Stream |
| Environment safety | PAPER hard lock | Demo/Testnet hard lock |
| SDK retry risk | RESTClient retries | ConfigurationRestAPI retries |

---

## 158. Decisions provisionally validated

### Decision 1

```text
Canonical OrderId remains provider-independent.
```

### Decision 2

```text
Provider client order reference must be first-class persistence metadata.
```

### Decision 3

```text
Unknown transport outcome must map to UNCERTAIN.
```

### Decision 4

```text
Blind automatic retry is forbidden for economic commands.
```

### Decision 5

```text
Private event streams are facts, not command acknowledgements.
```

### Decision 6

```text
Stream reconnect never replaces reconciliation.
```

### Decision 7

```text
Balance is independent from Position.
```

### Decision 8

```text
Provider constraints require a canonical extension point.
```

---

## 159. Decisions not yet validated

```text
global TradingMode enum
global Broker naming
canonical Fee model
canonical InstrumentTradingConstraints exact shape
canonical RateLimit model
provider clock sync contract
order book domain model
account activity model
```

Ne pas les figer avant le document comparatif.

---

## 160. Gate avant future Binance implementation

```text
[ ] Demo environment selected
[ ] LIVE hard lock defined
[ ] SDK pinned
[ ] retries disabled for command path
[ ] client order reference persistence proven
[ ] uncertain submit recovery proven
[ ] executionReport mappings captured
[ ] balance mappings defined
[ ] exchangeInfo mappings defined
[ ] filter validation defined
[ ] rate limit handling defined
[ ] clock skew handling defined
[ ] User Data Stream reconnect strategy defined
[ ] reconciliation defined
[ ] fixtures sanitized
[ ] no float economic truth
[ ] secrets redacted
```

---

## 161. Risk register

### R1 - Duplicate economic submit

Severity:

```text
CRITICAL
```

Cause:

```text
automatic SDK retry
manual retry after timeout
```

Mitigation:

```text
retries=0
client order reference
UNCERTAIN
query reconciliation
```

### R2 - Accidental LIVE trading

Severity:

```text
CRITICAL
```

Mitigation:

```text
explicit Demo/Testnet endpoint
fail closed
never SDK default base URL
```

### R3 - Rate limit ban

Severity:

```text
HIGH
```

Mitigation:

```text
weight tracking
Retry-After
429 backoff
418 circuit breaker
```

### R4 - Invalid order due to stale constraints

Severity:

```text
MEDIUM
```

Mitigation:

```text
exchangeInfo cache
refresh on rejection
provider final validation
```

### R5 - Stream gap

Severity:

```text
HIGH
```

Mitigation:

```text
reconnect
snapshot
reconciliation
Inbox
```

### R6 - Clock skew

Severity:

```text
MEDIUM/HIGH
```

Mitigation:

```text
server time probe
offset monitoring
small recvWindow with safety margin
```

### R7 - Decimal loss

Severity:

```text
HIGH
```

Mitigation:

```text
Decimal only
no float mappers
```

---

## 162. Recommended next action

Ne pas implémenter Binance maintenant.

Créer :

```text
41_PYTRADEKIT_BROKER_PROVIDER_COMPARATIVE_ARCHITECTURE.md
```

et confronter formellement :

```text
Alpaca
vs
Binance Spot
vs
current PyTradeKit ports
```

Le document doit identifier :

```text
what belongs to Domain
what belongs to Application
what belongs to Provider ACL
what belongs to Runtime
```

Ensuite seulement figer LOT-05.

---

## 163. Proposed refined discovery roadmap

```text
LOT-04A
Alpaca API & SDK analysis
DONE

LOT-04B
Binance Spot API & SDK comparative analysis
DONE with this document

LOT-04C
Provider comparative architecture
NEXT

LOT-04D
Alpaca PAPER read-only probes

LOT-04E
Alpaca controlled order probes

LOT-04F
Alpaca integration contract freeze

LOT-05
PAPER runtime configuration
```

Cette séquence est plus sûre que de définir le runtime immédiatement après une seule étude provider.

---

## 164. Why Binance should not enter 0.5 implementation

Ajouter Alpaca et Binance simultanément créerait trop de dimensions :

```text
equity vs crypto
session vs 24/7
position vs balance
PAPER vs Demo
two SDKs
two stream models
two market data stacks
two error models
two capability models
```

Cela rendrait impossible de savoir si un problème vient :

```text
du core
de l'ACL
du provider
du runtime
du modèle de données
```

Le bon ordre reste :

```text
design against two providers
implement one provider
qualify
then implement second provider
```

---

## 165. Final architecture insight

L'étude Binance révèle que PyTradeKit ne construit pas simplement un framework pour appeler des brokers.

Il construit une frontière de systèmes distribués entre :

```text
canonical trading intent
```

et :

```text
external trading venues
```

Chaque venue apporte :

```text
different identities
different order rules
different timing
different retries
different streams
different capabilities
different rate limits
different account semantics
different failure modes
```

Le rôle de PyTradeKit est de conserver :

```text
one coherent trading model
```

sans prétendre que tous les providers sont identiques.

---

## 166. Principle

Principe recommandé pour toute future intégration :

> Normalize semantics, not provider features.

Autrement dit :

```text
map common economic meaning
```

mais :

```text
do not erase provider-specific constraints
```

---

## 167. Architecture target

```text
                         PYTRADEKIT DOMAIN
                                |
        +-----------------------+-----------------------+
        |                       |                       |
        v                       v                       v
       OMS                  Portfolio                  Risk
        |                       |                       |
        +-----------------------+-----------------------+
                                |
                                v
                         Application Ports
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
      Alpaca Provider                         Binance Provider
             |                                     |
       +-----+------+                    +---------+---------+
       |            |                    |         |         |
       v            v                    v         v         v
   Trading API   Market Data          REST    User Data   Market
      PAPER                           DEMO      Stream     Streams
```

Le Domain ne dépend d'aucune des deux branches.

---

## 168. Validation des fondations existantes

Les LOT-01 à LOT-03 restent adaptés :

```text
Persistence Contracts
PostgreSQL
UnitOfWork
Outbox
Inbox
```

Binance renforce même leur pertinence.

Particulièrement :

```text
Inbox
```

pour dédupliquer les événements privés,

```text
Balance persistence
```

pour le Spot,

et :

```text
UnitOfWork
```

pour rendre atomique :

```text
event claim
order mutation
fill
balance mutation
outbox
```

---

## 169. PyTradeKit maturity implication

L'exercice Alpaca + Binance est un test d'architecture important.

Si les mêmes invariants restent valides :

```text
identity
certainty
idempotency
persistence
reconciliation
```

alors les fondations sont beaucoup plus crédibles qu'après une intégration single-provider.

---

## 170. Sources

### Binance Developer Documentation

```text
https://developers.binance.com/en/docs/products/spot/rest-api
https://developers.binance.com/en/docs/products/spot/web-socket-api
https://developers.binance.com/en/docs/products/spot/user-data-stream
https://developers.binance.com/en/docs/products/spot/filters
https://developers.binance.com/en/docs/products/spot/demo-mode/general-info
https://developers.binance.com/en/docs/products/spot/testnet
https://www.binance.com/en/binance-api
```

### Official SDK

```text
https://github.com/binance/binance-connector-python
```

### Official Postman collections

```text
https://github.com/binance/binance-api-postman
```

### PyTradeKit related analysis

```text
39_PYTRADEKIT_ALPACA_API_SDK_INTEGRATION_ANALYSIS.md
```

### Historical user integration

```text
ClientBinance
python-binance style Client
ThreadedWebsocketManager
```

Used only as historical implementation evidence, not as normative Binance API documentation.

---

## 171. Final conclusion

Binance Spot doit rester hors du code de PyTradeKit 0.5, mais il doit influencer immédiatement le design.

L'étude montre que plusieurs abstractions PyTradeKit résistent déjà au passage d'un broker equities à un crypto exchange :

```text
canonical identities
client order references
UNCERTAIN
no blind retry
Inbox
Outbox
reconciliation
Balance
Capabilities
Provider ACL
```

Elle révèle aussi les prochains points à consolider :

```text
InstrumentTradingConstraints
provider rate limit state
provider environment semantics
clock synchronization
fee asset representation
provider-neutral terminology
```

Le prochain document logique est donc :

```text
41_PYTRADEKIT_BROKER_PROVIDER_COMPARATIVE_ARCHITECTURE.md
```

Il devra servir de gate architectural avant le runtime PAPER final.

Le principe directeur est désormais clair :

> PyTradeKit ne doit être ni Alpaca-shaped ni Binance-shaped. Il doit fournir un modèle canonique capable d'intégrer les deux sans nier leurs différences opérationnelles.