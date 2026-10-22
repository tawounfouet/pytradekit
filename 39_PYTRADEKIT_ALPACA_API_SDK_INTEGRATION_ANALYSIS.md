# 39 - PyTradeKit - Alpaca API & SDK Integration Analysis

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Document :** Analyse d'intégration Alpaca API et SDK Python  
**Version :** 1.0  
**Date :** 2026-10-22  
**Statut :** Baseline d'architecture avant implémentation Alpaca  
**Périmètre :** Trading API, Market Data API, PAPER, `alpaca-py`, streaming, erreurs, retries, mappings et contraintes opérationnelles

---

## 1. Objet du document

Ce document constitue l'étude préalable obligatoire avant de définir le runtime PAPER et d'implémenter la couche Alpaca de PyTradeKit.

L'objectif n'est pas de reproduire l'API Alpaca dans PyTradeKit.

L'objectif est de comprendre précisément :

- quelles primitives Alpaca expose ;
- quelles garanties Alpaca fournit ;
- quelles garanties Alpaca ne fournit pas ;
- quels comportements sont propres au SDK `alpaca-py` ;
- quels états et événements doivent être traduits ;
- quels comportements doivent rester confinés dans l'infrastructure ;
- quelles contraintes doivent influencer la configuration runtime ;
- quelles hypothèses existantes de PyTradeKit sont confirmées ;
- quelles hypothèses doivent être corrigées avant toute implémentation.

La question centrale est :

> Quelles sont exactement les primitives, garanties, limitations, événements, états, erreurs et contraintes opérationnelles qu'Alpaca expose, et comment les traduire sans contaminer le modèle canonique PyTradeKit ?

---

## 2. Conclusion exécutive

L'étude confirme que PyTradeKit 0.5 doit intégrer Alpaca principalement via :

```text
Trading API
+
Market Data API
```

et non via :

```text
Broker API
```

Le Broker API vise la création et la gestion de comptes de courtage pour des utilisateurs tiers. Ce n'est pas le besoin de PyTradeKit 0.5, qui doit exécuter du PAPER trading sur un compte Alpaca contrôlé par l'utilisateur de PyTradeKit.

L'étude confirme également plusieurs décisions structurantes :

1. `PAPER` et `LIVE` utilisent des endpoints et des credentials différents.
2. `client_order_id` est une primitive essentielle et doit être générée et persistée avant tout submit.
3. Le cycle d'exécution repose sur une combinaison REST + WebSocket.
4. `trade_updates` doit être considéré comme un flux de faits externes, pas comme un simple callback technique.
5. Les snapshots account, positions, orders et market data doivent être séparés des commandes de trading.
6. Les flux Market Data et Trading sont techniquement distincts.
7. Les capacités Market Data dépendent du feed et du plan d'abonnement.
8. Le PAPER trading reproduit une partie utile du comportement réel, mais n'est pas une preuve d'équivalence LIVE.
9. Les IDs Alpaca ne doivent jamais remplacer les IDs canoniques PyTradeKit.
10. Le SDK `alpaca-py` doit rester confiné dans l'anti-corruption layer.
11. Le comportement de retry du SDK exige une décision d'architecture explicite avant d'utiliser `TradingClient.submit_order()`.

Le dernier point est critique.

Dans `alpaca-py` v0.44.0, le `RESTClient` utilise par défaut :

```text
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_WAIT_SECONDS = 3
DEFAULT_RETRY_EXCEPTION_CODES = [429, 504]
```

Le mécanisme est générique et est utilisé pour `GET`, `POST`, `PUT`, `PATCH` et `DELETE`.

Cela signifie qu'un `POST /orders` peut être automatiquement rejoué par le SDK après un `504`.

Pour PyTradeKit, ce comportement n'est pas acceptable par défaut.

La règle du framework reste :

```text
submit timeout / uncertain response
!=
rejection
!=
permission to retry blindly
```

Le chemin cible doit être :

```text
persist client_order_id
        |
        v
single submit attempt
        |
        +-------------------+
        |                   |
        v                   v
response known        response uncertain
        |                   |
        v                   v
map state           mark UNCERTAIN
                            |
                            v
                query by client_order_id
                            |
                +-----------+-----------+
                |                       |
                v                       v
             found                  not found
                |                       |
                v                       v
            converge          bounded reconciliation
```

Cette contrainte influence directement le design du futur adapter Alpaca.

---

## 3. Sources et statut des sources

### 3.1 Documentation officielle actuelle

Sources principales :

- Getting Started  
  https://docs.alpaca.markets/us/docs/getting-started

- Trading API Python SDK  
  https://alpaca.markets/sdks/python/api_reference/trading_api.html

- Market Data Python SDK  
  https://alpaca.markets/sdks/python/api_reference/data_api.html

- Paper Trading  
  https://docs.alpaca.markets/us/docs/paper-trading

- Trading authentication  
  https://docs.alpaca.markets/us/v1.1/docs/authentication-1

- Orders  
  https://docs.alpaca.markets/us/docs/orders-at-alpaca

- WebSocket Trading Stream  
  https://docs.alpaca.markets/us/docs/websocket-streaming

- Market Data plans and feeds  
  https://docs.alpaca.markets/us/docs/about-market-data-api

- Market Data FAQ  
  https://docs.alpaca.markets/us/docs/market-data-faq

- Positions  
  https://docs.alpaca.markets/us/docs/working-with-positions

- Account  
  https://docs.alpaca.markets/us/docs/working-with-account

- SDKs and tools  
  https://docs.alpaca.markets/us/docs/sdks-and-tools

### 3.2 SDK Python actif

Dépôt officiel actif :

```text
https://github.com/alpacahq/alpaca-py
```

Release étudiée :

```text
v0.44.0
published_at = 2026-08-11
```

Source :

```text
https://github.com/alpacahq/alpaca-py/releases/tag/v0.44.0
```

### 3.3 Ancien dépôt de documentation

Dépôt fourni initialement :

```text
https://github.com/alpacahq/alpaca-docs
```

État observé au 2026-10-22 :

```text
archived = true
default_branch = master
```

Ce dépôt peut rester utile pour du contexte historique, mais ne doit pas être utilisé comme source normative pour une nouvelle implémentation.

La priorité doit être :

```text
1. docs.alpaca.markets
2. alpaca-py actif
3. OpenAPI officielle
4. alpaca-docs archivé uniquement comme contexte secondaire
```

---

## 4. Positionnement exact du produit Alpaca dans PyTradeKit

Alpaca propose plusieurs surfaces fonctionnelles.

```text
Alpaca
|
+-- Trading API
|
+-- Market Data API
|
+-- Broker API
|
+-- Connect / OAuth
|
+-- Additional products
```

Pour PyTradeKit 0.5, le périmètre recommandé est :

```text
Trading API       IN
Market Data API   IN

Broker API        OUT
Connect / OAuth   OUT
Multi-user broker OUT
KYC               OUT
Funding / ACH     OUT
Account opening   OUT
```

### 4.1 Pourquoi Trading API

PyTradeKit doit :

- lire l'état d'un compte de trading ;
- lire les positions ;
- soumettre des ordres ;
- annuler des ordres ;
- interroger des ordres ;
- recevoir des mises à jour d'exécution.

Cela correspond à `TradingClient` et `TradingStream`.

### 4.2 Pourquoi Market Data API

PyTradeKit doit également pouvoir :

- lire une quote ;
- lire un trade ;
- lire des bars ;
- lire un snapshot ;
- éventuellement recevoir des quotes, trades et bars en temps réel.

Cela correspond aux clients Market Data, notamment :

```text
StockHistoricalDataClient
StockDataStream
```

### 4.3 Pourquoi Broker API est hors scope

Le SDK décrit `BrokerClient` comme la surface permettant de construire des produits d'investissement ou de courtage pour des comptes sous gestion.

Ce n'est pas le rôle de PyTradeKit 0.5.

Une intégration Broker API pourrait devenir un futur plugin ou module distinct, mais elle ne doit pas contaminer l'intégration PAPER actuelle.

---

## 5. Séparation PAPER / LIVE

### 5.1 Endpoints Trading

Alpaca définit explicitement deux environnements :

```text
PAPER
https://paper-api.alpaca.markets

LIVE
https://api.alpaca.markets
```

Le SDK encode également cette séparation dans `BaseURL` :

```text
TRADING_PAPER
TRADING_LIVE
TRADING_STREAM_PAPER
TRADING_STREAM_LIVE
```

### 5.2 Credentials

Les credentials PAPER sont différents des credentials LIVE.

Une configuration correcte doit donc vérifier ensemble :

```text
environment
endpoint
credentials
account identity
```

Il ne suffit pas d'avoir une clé valide.

### 5.3 Construction du SDK

Le SDK propose :

```python
TradingClient(
    api_key=...,
    secret_key=...,
    paper=True,
)
```

et :

```python
TradingStream(
    api_key=...,
    secret_key=...,
    paper=True,
)
```

### 5.4 Règle PyTradeKit 0.5

PyTradeKit 0.5 doit refuser toute configuration LIVE.

Cible :

```text
TradingEnvironment.PAPER -> allowed
TradingEnvironment.LIVE  -> rejected
```

Le runtime ne doit jamais faire :

```text
if no environment configured:
    fallback to live
```

Il doit faire l'inverse :

```text
if environment is not explicitly PAPER:
    fail startup
```

### 5.5 Invariant proposé

```text
PAPER readiness requires:

configured environment == PAPER
AND
trading REST endpoint == PAPER
AND
trading stream endpoint == PAPER
AND
credentials resolve successfully
AND
account identity matches expected identity
AND
account is usable for trading
```

---

## 6. SDK `alpaca-py`

### 6.1 Version étudiée

Version :

```text
alpaca-py 0.44.0
```

La release contient notamment :

- une évolution de validation des prix d'ordre indiquée comme breaking change ;
- des mises à jour importantes de dépendances ;
- une amélioration de la fiabilité de reconnexion streaming ;
- l'ajout de probes PAPER/sandbox.

Cela justifie un pin explicite lors de la première intégration.

Recommandation initiale :

```toml
alpaca = [
    "alpaca-py==0.44.0",
]
```

Une plage compatible pourra être ouverte plus tard, après qualification :

```toml
alpaca = [
    "alpaca-py>=0.44,<0.45",
]
```

### 6.2 SDK non autorisé dans le Domain

Règle :

```text
alpaca.*
```

ne doit être importé que dans :

```text
pytradekit.brokers.adapters.alpaca
```

ou un package d'infrastructure explicitement autorisé.

Fitness function future :

```text
FF-ALPACA-001
alpaca SDK imports are forbidden outside Alpaca infrastructure adapter
```

---

## 7. Clients SDK réellement utiles

L'idée d'un unique gros `AlpacaClient` est trop simplificatrice.

Le SDK expose plusieurs clients spécialisés.

Architecture provider observée :

```text
TradingClient
TradingStream
StockHistoricalDataClient
StockDataStream
```

PyTradeKit ne doit pas masquer artificiellement cette différence.

Architecture recommandée :

```text
                    PyTradeKit Canonical Ports
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
   ExecutionPort        SnapshotPort        MarketDataPort
          |                   |                   |
          +-------------------+-------------------+
                              |
                              v
                    Alpaca Anti-Corruption Layer
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
      TradingClient     TradingStream    Market Data Clients
         REST              WebSocket       REST / WebSocket
```

---

## 8. TradingClient

### 8.1 Responsabilités observées

`TradingClient` couvre notamment :

```text
submit_order
get_orders
get_order_by_id
get_order_by_client_id
replace_order_by_id
cancel_orders
cancel_order_by_id
get_all_positions
get_open_position
get_account
assets
clock
calendar
portfolio history
```

Le scope PyTradeKit 0.5 doit rester réduit.

### 8.2 Scope 0.5 recommandé

```text
submit_order             IN
get_orders               IN
get_order_by_id          IN
get_order_by_client_id   IN
cancel_order_by_id       IN
get_all_positions        IN
get_open_position        IN
get_account              IN
get_clock                OPTIONAL
get_calendar             OPTIONAL

replace_order_by_id      OUT
cancel_orders            OUT by default
close_all_positions      OUT
close_position           OUT
portfolio history        OUT
watchlists               OUT
options specific APIs    OUT
```

La règle reste : construire le plus petit vertical slice réel possible.

---

## 9. Ordres

### 9.1 Types supportés par le SDK

Le SDK expose notamment :

```text
MARKET
LIMIT
STOP
STOP_LIMIT
TRAILING_STOP
```

Mais 0.5 doit se limiter à :

```text
MARKET
LIMIT
CANCEL
```

### 9.2 Time in Force

Le SDK expose :

```text
DAY
GTC
OPG
CLS
IOC
FOK
```

Les combinaisons valides dépendent de la classe d'actif et du type d'ordre.

PyTradeKit ne doit pas supposer que tous les TIF sont supportés pour tous les instruments.

Cela doit devenir une capability contextuelle.

Exemple :

```text
supports(
    capability=LIMIT_ORDER,
    asset_class=US_EQUITY,
    time_in_force=DAY,
    environment=PAPER,
)
```

---

## 10. `client_order_id`

### 10.1 Support provider

L'API Alpaca accepte :

```text
client_order_id
```

avec une longueur maximale de 128 caractères.

Si le client ne le fournit pas, Alpaca en génère un.

PyTradeKit ne doit pas laisser Alpaca générer cet identifiant.

### 10.2 Règle PyTradeKit

PyTradeKit doit générer et persister un `client_order_id` avant le submit.

Exemple de format :

```text
PTKTEST-{canonical_order_uuid}
```

ou une forme compacte compatible avec la limite provider.

### 10.3 Utilité

Le `client_order_id` devient la clé principale de récupération après incertitude :

```text
canonical OrderId
        |
        v
persist client_order_id
        |
        v
submit to Alpaca
        |
        X
network uncertainty
        |
        v
get_order_by_client_id
```

### 10.4 Conséquence

Le `client_order_id` n'est pas un simple champ technique.

Il participe à la stratégie de sécurité contre le double submit.

---

## 11. IDs Alpaca et IDs PyTradeKit

Alpaca fournit un `Order.id` UUID provider.

PyTradeKit possède son propre `OrderId`.

Ils ne doivent jamais être confondus.

Cible :

```text
PyTradeKit OrderId
        |
        +-------------------------+
        |                         |
        v                         v
client_order_id          external_order_id
                            Alpaca Order.id
```

Même principe pour les fills :

```text
PyTradeKit FillId
!=
Alpaca execution_id
!=
account activity id
```

Règle d'architecture :

```text
Provider identifiers can correlate canonical objects.
Provider identifiers cannot replace canonical identities.
```

---

## 12. Cycle de vie des ordres Alpaca

### 12.1 OrderStatus du SDK

Le SDK v0.44.0 contient notamment :

```text
new
partially_filled
filled
done_for_day
canceled
expired
replaced
pending_cancel
pending_replace
pending_review
accepted
pending_new
accepted_for_bidding
stopped
rejected
suspended
calculated
held
```

Tous ces états ne doivent pas nécessairement être copiés dans le Domain PyTradeKit.

### 12.2 Principe de mapping

L'ACL doit convertir l'état provider vers le modèle canonique.

Exemple conceptuel :

```text
Alpaca                     PyTradeKit
------------------------------------------------
accepted                   SUBMITTED / ACKED
pending_new                SUBMITTED
new                        ACCEPTED
partially_filled           PARTIALLY_FILLED
filled                     FILLED
pending_cancel             CANCEL_REQUESTED
canceled                   CANCELED
expired                    EXPIRED
rejected                   REJECTED
```

Ce mapping doit être validé contre les transitions existantes de l'Order aggregate.

### 12.3 États rares

Les états suivants nécessitent une décision explicite :

```text
done_for_day
replaced
pending_replace
pending_review
accepted_for_bidding
stopped
suspended
calculated
held
```

Pour 0.5, deux approches sont possibles :

1. mapper vers un état canonique existant avec metadata provider ;
2. classer comme provider state non supporté et déclencher une reconciliation / degraded readiness.

Ne pas étendre le Domain uniquement pour refléter Alpaca.

---

## 13. TradingStream et `trade_updates`

### 13.1 Endpoint

Alpaca expose un WebSocket Trading Stream.

PAPER :

```text
wss://paper-api.alpaca.markets/stream
```

LIVE :

```text
wss://api.alpaca.markets/stream
```

### 13.2 Subscription

Le SDK expose :

```python
TradingStream.subscribe_trade_updates(handler)
```

### 13.3 TradeEvent du SDK

`alpaca-py` v0.44.0 expose :

```text
accepted
canceled
expired
fill
new
partial_fill
pending_cancel
pending_new
pending_replace
rejected
replaced
restated
```

### 13.4 TradeUpdate

Un `TradeUpdate` contient notamment :

```text
event
execution_id
order
timestamp
```

Selon l'événement, les données peuvent également contenir les informations d'exécution telles que quantité et prix.

### 13.5 Architecture PyTradeKit

Le flux ne doit pas entrer directement dans l'OMS.

Cible :

```text
Alpaca TradingStream
        |
        v
Raw provider message
        |
        v
Inbox claim
        |
        +-- duplicate -> stop
        |
        v
AlpacaTradeUpdateMapper
        |
        v
Canonical ExecutionReport / Fill
        |
        v
OMS handlers
        |
        v
Portfolio
        |
        v
Outbox
```

---

## 14. Reconnexion du TradingStream

La version v0.44.0 contient une logique de reconnexion avec backoff.

Valeurs observées dans le code :

```text
reconnect_min_backoff = 1.0
reconnect_max_backoff = 30.0
```

Le stream essaie de reconnecter après certaines erreurs WebSocket.

Cette fonctionnalité est utile, mais elle ne doit pas être interprétée comme une garantie métier.

Après une déconnexion, il existe une fenêtre pendant laquelle des événements peuvent ne pas être observés localement.

Donc :

```text
WebSocket reconnect
!=
state reconciliation
```

Le runtime doit toujours considérer :

```text
stream disconnected
        |
        v
reconnect
        |
        v
snapshot / reconciliation required
```

Cette responsabilité devient centrale dans 0.6.

---

## 15. Point critique - retry REST du SDK

### 15.1 Comportement observé

Dans `alpaca.common.rest.RESTClient`, la configuration par défaut est :

```text
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_WAIT_SECONDS = 3
DEFAULT_RETRY_EXCEPTION_CODES = [429, 504]
```

Le retry est implémenté dans `_request()`.

Cette méthode est appelée par :

```text
GET
POST
PUT
PATCH
DELETE
```

### 15.2 Risque

`TradingClient.submit_order()` appelle :

```text
self.post("/orders", data)
```

Le `POST` passe donc par le retry générique.

Scénario critique :

```text
POST /orders
        |
        v
Alpaca accepts order
        |
        v
gateway / network returns 504
        |
        v
SDK sees 504
        |
        v
automatic retry
        |
        v
second POST /orders
```

Même si `client_order_id` apporte une protection importante, PyTradeKit ne doit pas déléguer son invariant de non-répétition à un comportement implicite du provider.

### 15.3 Décision recommandée

Les lectures peuvent utiliser le comportement de retry SDK sous contrôle :

```text
GET account
GET order
GET positions
GET market data
```

Les commandes avec effet métier doivent utiliser une politique spécifique :

```text
submit order
cancel order
future replace order
future close position
```

Pour `submit order`, la cible recommandée est :

```text
exactly one transport attempt
```

puis :

```text
uncertain -> reconciliation by client_order_id
```

### 15.4 Options techniques

#### Option A - SDK direct partout

Rejetée pour la première implémentation.
Raison :

```text
generic POST retry policy
```

#### Option B - subclass du SDK et modification des attributs privés

Possible techniquement mais fragile.

Exemple conceptuel :

```text
_retry
_retry_codes
```

sont des détails d'implémentation privés.

Cette solution créerait une dépendance forte aux internals de `alpaca-py`.

#### Option C - SDK pour models/read paths + transport contrôlé pour command path

Recommandée.

Architecture :

```text
Alpaca SDK
|
+-- request / response models
+-- read clients
+-- stream clients
|
+-- command transport PyTradeKit
    |
    +-- no automatic retry for submit
```

#### Option D - client HTTP Alpaca entièrement propriétaire

Possible mais probablement excessif pour 0.5.

### 15.5 Décision provisoire

Recommandation :

```text
Use alpaca-py for:
- request/response model compatibility
- read operations
- WebSocket streams
- market data

Use a PyTradeKit controlled transport boundary for:
- order submission
```

Cette décision doit être prototypée dans LOT-04 avant de figer LOT-06.

---

## 16. Erreurs Alpaca

### 16.1 APIError SDK

Le SDK expose :

```text
APIError
```

avec notamment :

```text
code
message
status_code
request
response
```

### 16.2 Mapping cible

PyTradeKit doit produire des erreurs canoniques.

Exemple :

```text
Alpaca APIError
        |
        v
AlpacaErrorMapper
        |
        +-- AuthenticationError
        +-- AuthorizationError
        +-- RateLimitError
        +-- BrokerRejectedOrder
        +-- ValidationError
        +-- ProviderUnavailable
        +-- ProviderProtocolError
        +-- UnknownSubmissionOutcome
```

Les noms exacts doivent être alignés sur les erreurs déjà présentes dans PyTradeKit.

### 16.3 HTTP 429

Market Data documente explicitement `429 Too Many Requests`.

Le SDK peut retry automatiquement les `429`.

Pour les reads, un retry borné peut être acceptable.

Pour les writes, la policy doit rester explicite.

### 16.4 HTTP 504

Le retry automatique du SDK sur `504` est le cas le plus sensible pour les commandes.

Règle :

```text
504 after submit
= submission outcome uncertain
```

et non :

```text
504 after submit
= submit again
```

---

## 17. Request ID

Alpaca fournit un header :

```text
X-Request-ID
```

sur les appels Trading API.

La documentation recommande de conserver les IDs récents car ils facilitent le support et le diagnostic.

PyTradeKit devrait introduire une capture infrastructure :

```text
BrokerRequestTrace
```

avec au minimum :

```text
provider
operation
request_id
correlation_id
canonical_order_id
client_order_id
external_order_id
occurred_at
outcome
```

Ce record ne doit pas devenir un objet du Domain trading.

Il appartient à :

```text
observability
audit
infrastructure
```

---

## 18. Account snapshot

### 18.1 Source

`TradingClient.get_account()` retourne un `TradeAccount`.

La documentation expose notamment :

```text
buying_power
cash
equity
portfolio_value
trading_blocked
```

### 18.2 Mapping PyTradeKit

Attention à ne pas faire :

```text
buying_power == cash
```

ou :

```text
buying_power == Balance.available
```

sans contrat sémantique explicite.

Le buying power dépend des règles de marge et du compte.

Recommandation :

```text
BrokerAccountSnapshot
    provider_account_id
    status
    cash
    equity
    portfolio_value
    buying_power
    trading_blocked
    observed_at
```

Puis un mapping explicite vers les objets Portfolio seulement pour les champs dont la sémantique correspond réellement.

---

## 19. Positions snapshot

### 19.1 Source

`TradingClient.get_all_positions()` expose les positions ouvertes.

Le modèle SDK contient notamment :

```text
asset_id
symbol
exchange
asset_class
avg_entry_price
qty
side
market_value
cost_basis
unrealized_pl
current_price
qty_available
```

### 19.2 Mapping canonique

PyTradeKit doit utiliser son `InstrumentId`.

Donc :

```text
Alpaca symbol
        |
        v
InstrumentMapping
        |
        v
PyTradeKit InstrumentId
```

Jamais :

```text
InstrumentId = symbol
```

### 19.3 Position side

Alpaca expose explicitement :

```text
long
short
```

Le modèle canonique PyTradeKit doit conserver sa propre représentation de position.

---

## 20. Fill et execution identity

Alpaca fournit plusieurs sources utiles :

```text
TradingStream TradeUpdate.execution_id
Account Activities FILL id
Order filled quantities
```

Ces identifiants peuvent avoir des usages différents.

Il faut éviter de supposer immédiatement :

```text
TradeUpdate.execution_id
==
AccountActivity.id
```

Le document officiel ne garantit pas ici une égalité sémantique générale.

Décision recommandée :

```text
external_fill_id
```

doit être obtenu à partir de la source utilisée pour créer le Fill canonique.

Pour le vertical slice 0.5 :

```text
trade_updates fill / partial_fill
```

peut fournir la première source.

La réconciliation 0.6 pourra utiliser Account Activities comme source supplémentaire de vérité.

---

## 21. Market Data

### 21.1 Clients

Pour les actions, `alpaca-py` distingue :

```text
StockHistoricalDataClient
StockDataStream
```

### 21.2 Historical / latest

Le client historique couvre notamment :

```text
bars
quotes
trades
latest bar
latest quote
latest trade
snapshot
```

### 21.3 Streaming

`StockDataStream` couvre notamment :

```text
subscribe_quotes
subscribe_trades
subscribe_bars
```

### 21.4 Conséquence architecturale

Éviter un unique adapter opaque.

Préférer :

```text
AlpacaHistoricalMarketDataAdapter
AlpacaRealtimeMarketDataAdapter
AlpacaSnapshotAdapter
```

ou plusieurs classes internes derrière un port public cohérent.

---

## 22. Market Data feeds

Le SDK expose `DataFeed` :

```text
IEX
SIP
DELAYED_SIP
OTC
BOATS
OVERNIGHT
```

### 22.1 Basic plan

Au moment de cette étude, Alpaca documente pour les actions :

```text
Basic:
real-time feed = IEX
WebSocket symbols = 30
historical calls = 200 / min
historical restriction = latest 15 minutes
```

### 22.2 Algo Trader Plus

La documentation indique :

```text
all US stock exchanges
unlimited WebSocket subscriptions
10,000 historical calls / min
no 15-minute historical restriction
```

### 22.3 Conséquence

Une capability booléenne :

```text
REALTIME_QUOTES = true
```

est trop faible.

Il faut représenter le contexte :

```text
MarketDataCapabilitySnapshot
    asset_class
    feed
    realtime
    websocket_symbol_limit
    historical_rate_limit
    historical_freshness_limit
    observed_at
```

---

## 23. Symbol changes et `asof`

La Market Data API dispose d'un comportement de résolution historique des changements de ticker via `asof`.

Exemple documenté par Alpaca :

```text
FB -> META
```

Le stream temps réel, lui, nécessite de se réabonner au nouveau symbole.

Conséquence PyTradeKit :

```text
historical instrument identity
!=
stream subscription symbol identity
```

Le registre d'instruments et les mappings provider restent donc essentiels.

---

## 24. Market clock et calendar

Le SDK fournit :

```text
Clock
Calendar
```

avec notamment :

```text
is_open
next_open
next_close
market dates
open / close times
```

Ces informations peuvent être utiles pour :

```text
readiness diagnostics
demo orchestration
qualification PAPER
```

Mais PyTradeKit ne doit pas faire du clock provider sa seule source temporelle interne.

Le `ClockPort` canonique reste indépendant.

Le clock Alpaca est une observation provider.

---

## 25. Cancel semantics

`TradingClient.cancel_order_by_id()` appelle :

```text
DELETE /orders/{id}
```

et ne retourne actuellement pas de statut métier détaillé dans le SDK.

Le code du SDK contient même un commentaire indiquant qu'il serait préférable de retourner davantage d'informations sur l'état du cancel.

Conséquence majeure :

```text
cancel request accepted
!=
order canceled
```

PyTradeKit doit donc conserver :

```text
CANCEL_REQUESTED
```

puis attendre :

```text
trade_update canceled
```

ou faire une query / reconciliation.

Le vertical slice doit tester la race :

```text
cancel requested
        |
        +----------------+
        |                |
        v                v
cancel event          fill event
        |                |
        v                v
CANCELED            FILLED/PARTIAL
```

---

## 26. PAPER semantics

### 26.1 Ce que PAPER fournit

La documentation présente PAPER comme un environnement de simulation temps réel utilisant les quotes réelles.

Les API specs PAPER et LIVE sont décrites comme identiques côté interface.

Cela rend PAPER particulièrement adapté pour tester :

```text
authentication
order submission
order lifecycle
partial fills
streaming
cancel flows
network handling
runtime startup
persistence
restart
reconciliation baseline
```

### 26.2 Partial fills

Alpaca documente un comportement de partial fill dans l'environnement PAPER.

Cela signifie que PyTradeKit peut réellement qualifier :

```text
PARTIAL_FILL
```

sans construire uniquement un scénario simulé interne.

### 26.3 Limites de PAPER

La documentation prévient que PAPER ne reproduit pas complètement le marché réel.

Parmi les différences signalées :

```text
market impact
latency slippage
queue position
price improvement
regulatory fees
dividends
```

Conclusion :

```text
PAPER qualification
!=
LIVE equivalence
```

### 26.4 Compliance level

Recommandation :

```text
0.5:
C2 Integration Qualified
+
selected early C3 evidence
```

et non :

```text
full production proven
```

---

## 27. Authentication et secrets

### 27.1 Trading API

Credentials :

```text
APCA-API-KEY-ID
APCA-API-SECRET-KEY
```

### 27.2 Règle PyTradeKit

La config ne contient jamais directement :

```text
api_key
secret_key
```

Elle contient des références :

```text
secret://alpaca/paper/api_key
secret://alpaca/paper/secret_key
```

résolues via :

```text
SecretsPort
```

### 27.3 Redaction

Interdire dans les logs :

```text
API key
secret key
Authorization
database password
full raw auth headers
```

Tests requis :

```text
secret redaction
exception redaction
config dump redaction
structured log redaction
```

---

## 28. Architecture Anti-Corruption Layer

Structure cible recommandée :

```text
src/pytradekit/brokers/adapters/alpaca/
|
+-- __init__.py
|
+-- config.py
|
+-- sdk/
|   +-- trading_reads.py
|   +-- trading_stream.py
|   +-- market_data.py
|
+-- transport/
|   +-- command_transport.py
|   +-- request_trace.py
|
+-- execution.py
|
+-- snapshots.py
|
+-- market_data.py
|
+-- stream.py
|
+-- capabilities.py
|
+-- manifest.py
|
+-- errors.py
|
+-- mappers/
    +-- instrument.py
    +-- order.py
    +-- execution.py
    +-- account.py
    +-- position.py
    +-- market_data.py
```

Principe :

```text
Domain
  |
  v
Port
  |
  v
Alpaca Adapter
  |
  v
Alpaca SDK / HTTP
```

Jamais :

```text
Domain
  |
  v
alpaca.trading.*
```

---

## 29. Runtime PAPER après l'étude provider

Le runtime peut maintenant être défini sur des faits réels.

### 29.1 Configuration minimale

```text
RuntimeProfile
    environment = PAPER

AlpacaTradingConfig
    provider = ALPACA
    paper = true
    api_key_ref
    secret_key_ref
    expected_account_id
    command_timeout
    query_timeout

AlpacaMarketDataConfig
    feed = IEX
    websocket_enabled
    freshness_threshold
```

### 29.2 Runtime startup proposé

```text
01 load runtime profile
02 require PAPER
03 resolve secrets
04 initialize database
05 verify migration level
06 initialize safe Alpaca command transport
07 initialize TradingClient read path
08 initialize TradingStream
09 initialize Market Data clients
10 get account
11 verify expected account identity
12 verify account trading state
13 detect capabilities / configured feed
14 load unresolved local orders
15 perform minimal startup reconciliation
16 start trade_updates stream
17 establish market data readiness if required
18 expose READY
```

### 29.3 LIVE safety

Hard blocker :

```text
paper = false
=> startup failure
```

dans 0.5.

---

## 30. Snapshot model

Le SnapshotAdapter doit être capable de fournir :

```text
BrokerSnapshot
|
+-- account
|
+-- open_orders
|
+-- recent_orders
|
+-- positions
|
+-- balances / cash observations
|
+-- recent fills where available
|
+-- observed_at
|
+-- completeness
```

Le snapshot est utilisé pour :

```text
startup reconciliation
manual diagnostics
readiness
future 0.6 recovery
```

---

## 31. Startup reconciliation 0.5

Le scope doit rester borné.

Local unresolved states :

```text
SUBMITTED without external_order_id
UNCERTAIN
CANCEL_REQUESTED
```

Flow :

```text
load unresolved order
        |
        v
if client_order_id exists
        |
        v
get_order_by_client_id
        |
        +-- found
        |     |
        |     v
        |  map provider state
        |     |
        |     v
        |  persist external_order_id
        |
        +-- not found
              |
              v
        remain unresolved
```

Règle :

```text
not found
!=
safe automatic resubmit
```

La policy de resubmit doit être explicitement définie et probablement repoussée à 0.6.

---

## 32. Inbox et trade updates

Le LOT-03 a déjà préparé :

```text
Inbox
ProcessedFillRegistry
Outbox
UnitOfWork
```

L'intégration Alpaca doit exploiter directement ces primitives.

Flow cible :

```text
TradeUpdate arrives
        |
        v
compute provider event identity
        |
        v
Inbox.claim(...)
        |
        +-- false -> duplicate, stop
        |
        v
map event
        |
        v
apply OMS mutation
        |
        v
create Fill if economic execution
        |
        v
update Portfolio
        |
        v
insert Outbox
        |
        v
mark Inbox processed
        |
        v
COMMIT
```

Atomicité recherchée :

```text
Inbox claim
+
Domain state
+
Fill
+
Portfolio
+
Outbox

same local transaction
```

---

## 33. Event identity strategy

Toutes les TradeUpdates ne fournissent pas nécessairement une identité uniforme de la même nature.

Pour un fill :

```text
execution_id
```

est une excellente candidate.

Pour les autres événements, il faut définir une clé stable.

Exemple possible :

```text
provider
+
order.id
+
event
+
timestamp
+
selected provider fields
```

Mais cette stratégie ne doit pas être inventée sans test réel.

LOT-04 doit donc inclure une capture contrôlée de vrais messages PAPER pour :
```text
new
fill
partial_fill
pending_cancel
canceled
rejected
```

---

## 34. Capability model Alpaca

Capabilities de base 0.5 :

```text
PAPER
MARKET_ORDER
LIMIT_ORDER
CANCEL
ORDER_QUERY
POSITION_QUERY
ACCOUNT_QUERY
REALTIME_ORDER_UPDATES
HISTORICAL_BARS
LATEST_QUOTES
REALTIME_QUOTES
```

Mais elles doivent être contextualisées.

Exemple :

```text
CapabilityContext
    provider = ALPACA
    environment = PAPER
    asset_class = US_EQUITY
    feed = IEX
```

Puis :

```text
supports(MARKET_ORDER, context) -> yes
supports(LIMIT_ORDER, context)  -> yes
supports(SIP_REALTIME, context) -> depends on subscription
```

---

## 35. Broker manifest

Proposition :

```text
BrokerAdapterManifest
    provider
    adapter_version
    sdk_name
    sdk_version
    supported_environment
    supported_asset_classes
    order_capabilities
    market_data_capabilities
    stream_capabilities
    retry_policy
    reconciliation_features
```

Exemple :

```text
provider = alpaca
sdk_name = alpaca-py
sdk_version = 0.44.0
environment = PAPER only
```

---

## 36. Observabilité

Minimum :

```text
alpaca_requests_total
alpaca_request_failures_total
alpaca_request_latency_seconds
alpaca_rate_limit_total

alpaca_trade_stream_connected
alpaca_trade_stream_reconnect_total
alpaca_trade_updates_total

alpaca_order_submit_total
alpaca_order_submit_uncertain_total
alpaca_order_cancel_total

alpaca_inbox_duplicate_total

alpaca_snapshot_age_seconds
alpaca_reconciliation_unresolved_total
```

Logs structurés :

```text
provider
operation
canonical_order_id
client_order_id
external_order_id
request_id
correlation_id
status
duration_ms
```

Sans secret.

---

## 37. Rate limits

Les limites ne doivent pas être hardcodées comme constantes universelles du Domain.

Elles appartiennent aux capabilities / runtime provider.

Exemple :

```text
MarketDataRateProfile
    historical_requests_per_minute
    websocket_symbol_limit
    feed
    freshness_restriction
```

En cas de `429` :

```text
read path
-> bounded retry / backoff may be allowed

write path
-> no generic blind retry
```

---

## 38. Extended hours

L'API Create Order expose `extended_hours`.

La documentation indique des restrictions de combinaison, notamment avec des ordres limit et certains TIF.

0.5 ne doit pas activer les extended hours par défaut.

Recommandation :

```text
extended_hours = false
```

Le support explicite pourra venir plus tard via capability dédiée.

---

## 39. Asset scope 0.5

Le SDK supporte :

```text
US_EQUITY
US_OPTION
CRYPTO
CRYPTO_PERP
```

Mais PyTradeKit 0.5 ne doit pas essayer de qualifier toutes les classes d'actifs.

Recommandation :

```text
P0 = US_EQUITY
```

Éventuellement :

```text
crypto = later
options = later
```

Raison :

- réduire les règles de TIF ;
- réduire les contraintes fractional/notional ;
- réduire les horaires spécifiques ;
- simplifier le mapping instrument ;
- simplifier les scénarios E2E PAPER.

---

## 40. Instruments de qualification

Choisir des instruments :

```text
liquides
US equity
tradables
fractionable if useful
stable provider mapping
```

Ne pas hardcoder le symbole dans le Domain.

Les tests PAPER peuvent utiliser un ensemble configuré :

```text
ALPACA_PAPER_TEST_SYMBOLS
```

Le choix réel doit être vérifié au runtime.

---

## 41. Market hours

Les scénarios MARKET réels dépendent de l'ouverture du marché.

Le test suite doit distinguer :

```text
deterministic mapping tests
integration tests with mocked provider
real PAPER tests requiring market state
```

Les real PAPER tests ne doivent pas rendre la CI standard dépendante des horaires boursiers.

Recommandation :

```text
pytest -m alpaca_paper
```

et exécution contrôlée séparément.

---

## 42. Types numériques

Le SDK expose de nombreux champs numériques provider sous forme de chaînes :

```text
qty
filled_qty
limit_price
avg_entry_price
cash
buying_power
```

PyTradeKit doit convertir immédiatement vers :

```text
Decimal
Money
Price
Quantity
```

Jamais :

```text
float
```

pour la vérité économique canonique.

---

## 43. Time semantics

Alpaca retourne des timestamps avec timezone.

PyTradeKit doit :

```text
parse provider timezone
        |
        v
normalize UTC
        |
        v
canonical UTC datetime
```

Les timestamps provider sont des observations.

Ils ne doivent pas être remplacés par `now()` lors du mapping si le provider fournit une heure d'événement.

---

## 44. Data freshness

Les snapshots doivent porter explicitement :

```text
observed_at
```

et idéalement :

```text
provider_timestamp
received_at
```

Une quote sans notion de freshness ne doit pas être utilisée implicitement dans Risk.

Exemple de future règle :

```text
if quote_age > threshold:
    reject risk valuation / degrade readiness
```

---

## 45. Design proposé des adapters

### 45.1 Execution

```text
AlpacaExecutionAdapter
|
+-- submit_market
+-- submit_limit
+-- request_cancel
+-- query_order
```

### 45.2 Stream

```text
AlpacaTradeUpdateReceiver
|
+-- connect
+-- subscribe
+-- normalize raw event
+-- deliver to Inbox handler
```

### 45.3 Snapshots

```text
AlpacaSnapshotAdapter
|
+-- account_snapshot
+-- position_snapshot
+-- order_snapshot
+-- recent_fill_snapshot
```

### 45.4 Market Data

```text
AlpacaHistoricalMarketDataAdapter
AlpacaRealtimeMarketDataAdapter
```

### 45.5 Capabilities

```text
AlpacaCapabilityProvider
```

---

## 46. API surface à ne pas exposer

PyTradeKit public API ne doit pas exposer :

```text
TradingClient
TradingStream
StockHistoricalDataClient
StockDataStream
alpaca.trading.models.Order
alpaca.trading.models.Position
alpaca.trading.enums.*
alpaca.data.enums.*
APIError
```

Le consommateur doit voir :

```text
PyTradeKit canonical types
```

---

## 47. Tests à construire avant le vrai E2E

### 47.1 Mapping

```text
Alpaca Order -> canonical broker order snapshot
TradeUpdate -> ExecutionReport
TradeUpdate partial_fill -> Fill
TradeAccount -> BrokerAccountSnapshot
Position -> canonical position observation
Quote -> canonical Quote
Bar -> canonical Bar
```

### 47.2 Error mapping

```text
401
403
404
422 / validation
429
500
504
network timeout
connection error
stream auth failure
```

### 47.3 Command safety

```text
submit called once
timeout after send
no automatic resubmit
query by client_order_id
recover accepted order
```

### 47.4 Stream

```text
duplicate fill
out-of-order event
disconnect
reconnect
event after reconnect
```

### 47.5 PAPER hard-lock

```text
paper=false -> rejected
live endpoint -> rejected
unexpected account -> not READY
```

---

## 48. Real PAPER discovery tests

Avant l'adapter final, LOT-04 doit inclure un mini programme de probes.

Probes recommandées :

```text
01 authenticate PAPER
02 read account
03 read clock
04 read asset
05 read latest quote
06 submit tiny MARKET order
07 observe REST response
08 observe trade_updates
09 query order by external id
10 query order by client_order_id
11 query positions
12 submit LIMIT away from market
13 cancel LIMIT
14 observe pending_cancel / canceled if emitted
15 capture request IDs
16 restart stream
17 inspect reconnect behavior
```

Ces probes ne doivent pas encore devenir le runtime final.

Leur objectif est de produire des fixtures provider réelles.

---

## 49. Fixtures provider

Après les probes, conserver des fixtures nettoyées :

```text
tests/fixtures/alpaca/
|
+-- order_market_submitted.json
+-- order_limit_open.json
+-- trade_update_new.json
+-- trade_update_partial_fill.json
+-- trade_update_fill.json
+-- trade_update_pending_cancel.json
+-- trade_update_canceled.json
+-- account.json
+-- positions.json
+-- latest_quote.json
```

Aucun secret ni identifiant personnel sensible.

---

## 50. Décisions architecture validées

### ADR candidate - Alpaca SDK isolation

```text
Decision:
alpaca-py is confined to the Alpaca adapter boundary.
```

### ADR candidate - command retry safety

```text
Decision:
order submission must not inherit generic SDK automatic retry behavior.
```

### ADR candidate - client order identity

```text
Decision:
client_order_id is persisted before submit and is mandatory for Alpaca orders.
```

### ADR candidate - WebSocket is not reconciliation

```text
Decision:
stream reconnect never substitutes startup or recovery reconciliation.
```

### ADR candidate - provider state is not domain state

```text
Decision:
Alpaca statuses are mapped, not copied wholesale into the Domain.
```

### ADR candidate - PAPER hard-lock

```text
Decision:
PyTradeKit 0.5 supports Alpaca PAPER only and refuses LIVE startup.
```

---

## 51. Questions ouvertes

Avant de clôturer LOT-04, répondre expérimentalement à :

1. Comment Alpaca réagit-il à un second submit avec le même `client_order_id` ?
2. Quel HTTP status et quel error code sont retournés ?
3. Peut-on récupérer systématiquement l'ordre via `get_order_by_client_id` immédiatement après un timeout simulé ?
4. Quel identifiant est le plus stable pour dédupliquer chaque type de `trade_update` ?
5. `execution_id` est-il toujours présent sur `fill` et `partial_fill` ?
6. Quel délai est observé entre REST ACK et `trade_updates` ?
7. Quels événements sont réellement observés sur un MARKET PAPER simple ?
8. Quels événements sont réellement observés sur LIMIT puis CANCEL ?
9. Après reconnexion du TradingStream, Alpaca rejoue-t-il des événements manqués ?
10. Si non, quel snapshot minimal permet de converger ?
11. Quels champs Account doivent alimenter Balance vs BrokerAccountSnapshot ?
12. Quelles limites Market Data sont réellement actives sur le compte PAPER utilisé ?
13. Quel feed est effectivement retourné par défaut ?
14. Les IDs d'assets Alpaca sont-ils suffisamment stables pour servir de mapping externe long terme ?
15. Quelle stratégie exacte adopter pour capturer `X-Request-ID` si on utilise partiellement `alpaca-py` ?

---

## 52. Ordre corrigé du milestone 0.5

```text
LOT-01 - Persistence Contracts
DONE

LOT-02 - PostgreSQL + Migrations
DONE

LOT-03 - UnitOfWork + Outbox + Inbox
DONE

LOT-04 - Alpaca API & SDK Discovery
NEXT

LOT-05 - PAPER Runtime Configuration

LOT-06 - Alpaca Anti-Corruption Layer

LOT-07 - Alpaca Execution

LOT-08 - Alpaca Market Data & Snapshots

LOT-09 - Startup, Restart & E2E

LOT-10 - Qualification
```

---

## 53. LOT-04 - Alpaca API & SDK Discovery

### Scope

```text
Trading API analysis
Market Data API analysis
Paper semantics
alpaca-py v0.44.0 analysis
REST behavior
WebSocket behavior
request / response models
order lifecycle
client_order_id
error model
retry behavior
rate limits
feeds
account semantics
position semantics
timeouts
stream reconnect
real PAPER probes
provider fixtures
```

### Deliverables

```text
39_PYTRADEKIT_ALPACA_API_SDK_INTEGRATION_ANALYSIS.md

docs/provider/alpaca/
    PAPER_DISCOVERY_NOTES.md
    STATUS_MAPPING.md
    ERROR_MAPPING.md
    CAPABILITY_MATRIX.md

tests/fixtures/alpaca/
    sanitized provider fixtures

scripts/
    alpaca_paper_probe.py
```

Le script probe n'est pas un composant de production.

---

## 54. Gate LOT-04

LOT-04 est terminé uniquement si :

```text
[ ] Trading API surface required by 0.5 is documented
[ ] Market Data surface required by 0.5 is documented
[ ] Broker API is confirmed out of scope
[ ] PAPER and LIVE boundaries are explicit
[ ] alpaca-py version is pinned for qualification
[ ] SDK retry behavior is documented
[ ] safe submit strategy is selected
[ ] client_order_id recovery path is proven
[ ] relevant OrderStatus mapping is specified
[ ] TradeEvent mapping is specified
[ ] account mapping is specified
[ ] position mapping is specified
[ ] Market Data feed capability is specified
[ ] WebSocket reconnect semantics are understood
[ ] real PAPER fixtures are captured
[ ] no secrets are present in fixtures
[ ] PAPER-only hard-lock requirements are defined
[ ] runtime configuration can now be designed from provider facts
```

---

## 55. Gate de sécurité avant LOT-05

LOT-05 ne doit pas commencer si la question suivante n'a pas de réponse ferme :

```text
How do we guarantee that one PyTradeKit submit command
cannot become two Alpaca order submissions
because of SDK or transport retry behavior?
```

La réponse attendue doit être démontrée par test.

---

## 56. Impact sur la spec 0.5 existante

La spec initiale reste globalement valide sur :

```text
PostgreSQL
UnitOfWork
Outbox
Inbox
SecretsPort
PAPER profile
client_order_id
startup reconciliation
capabilities
snapshots
real PAPER E2E
```

Elle doit être amendée sur :

```text
LOT ordering
AlpacaClient abstraction
retry assumptions
market data capability richness
streaming architecture
provider probe phase
```

En particulier, remplacer l'idée :

```text
AlpacaClient
```

comme unique façade technique par une architecture plus explicite :

```text
AlpacaExecutionAdapter
        |
        +-- safe command transport
        |
        +-- TradingClient read path

AlpacaTradeUpdateReceiver
        |
        +-- TradingStream

AlpacaHistoricalMarketDataAdapter
        |
        +-- StockHistoricalDataClient

AlpacaRealtimeMarketDataAdapter
        |
        +-- StockDataStream
```

---

## 57. Architecture cible révisée

```text
                          PYTRADEKIT DOMAIN
                                 |
               +-----------------+-----------------+
               |                 |                 |
               v                 v                 v
           OMS / Orders       Portfolio          Risk
               |                 |                 |
               +-----------------+-----------------+
                                 |
                                 v
                         Application Layer
                                 |
               +-----------------+-----------------+
               |                 |                 |
               v                 v                 v
        ExecutionPort       SnapshotPort      MarketDataPort
               |                 |                 |
               +-----------------+-----------------+
                                 |
                                 v
                      ALPACA ANTI-CORRUPTION LAYER
                                 |
          +----------------------+----------------------+
          |                      |                      |
          v                      v                      v
 Safe Command Transport   Trading Read Client    Trading Stream
          |                      |                      |
          v                      v                      v
 POST /orders          TradingClient          TradingStream
 no blind retry        query snapshots        trade_updates
          |                      |                      |
          +----------------------+----------------------+
                                 |
                                 v
                           Alpaca PAPER
                                 |
               +-----------------+-----------------+
               |                                   |
               v                                   v
        Trading API                         Market Data API
                                                |
                              +-----------------+-----------------+
                              |                                   |
                              v                                   v
                 StockHistoricalDataClient               StockDataStream
```

---

## 58. Interaction avec Persistence LOT-01 à LOT-03

Les trois premiers lots deviennent la fondation de l'intégration provider.

```text
Alpaca REST / WS
       |
       v
Adapter
       |
       v
Inbox
       |
       v
Canonical event
       |
       v
OMS / Portfolio
       |
       v
Repositories
       |
       v
Outbox
       |
       v
COMMIT PostgreSQL
```

Cela valide le choix d'avoir implémenté la persistence avant Alpaca.

La persistence ne dépend pas d'Alpaca.

Alpaca dépend des contrats de persistence et d'idempotence déjà établis.

---

## 59. Critères de non-contamination du Domain

Après intégration Alpaca, ces recherches doivent retourner zéro résultat dans les packages Domain :

```text
alpaca
TradingClient
TradingStream
StockHistoricalDataClient
StockDataStream
APIError
DataFeed
OrderStatus from Alpaca
TradeEvent from Alpaca
```

Le Domain doit continuer à fonctionner :

```text
without alpaca-py installed
```

sauf si l'utilisateur installe explicitement l'extra Alpaca.

Recommandation future :

```toml
[project.optional-dependencies]
alpaca = [
    "alpaca-py==0.44.0",
]
```

et éventuellement :

```text
pytradekit[postgres,alpaca]
```

pour le runtime PAPER.

---

## 60. Risques principaux

### R1 - Double submit via retry SDK

Sévérité :

```text
CRITICAL
```

Mitigation :

```text
safe command transport
client_order_id
no blind retry
uncertain state
query recovery
```

### R2 - Confusion PAPER / LIVE

Sévérité :

```text
CRITICAL
```

Mitigation :

```text
hard PAPER lock
endpoint verification
credential/account verification
```

### R3 - Duplicate stream event

Sévérité :

```text
HIGH
```

Mitigation :

```text
Inbox
ProcessedFillRegistry
unique fill identity
```

### R4 - Missed event during disconnect

Sévérité :

```text
HIGH
```

Mitigation :

```text
reconnect
snapshot
reconciliation
```

### R5 - Provider state leakage

Sévérité :

```text
MEDIUM
```

Mitigation :

```text
ACL mappings
canonical enums
architecture tests
```

### R6 - Market Data feed assumption

Sévérité :

```text
MEDIUM
```

Mitigation :

```text
capability snapshot
explicit feed
freshness metadata
```

### R7 - SDK breaking change
Sévérité :

```text
MEDIUM
```

Mitigation :

```text
version pin
contract tests
upgrade qualification
```

---

## 61. Décision finale

Il est trop tôt pour implémenter le runtime PAPER final.

La prochaine étape correcte est :

```text
LOT-04
Alpaca API & SDK Discovery
```

avec deux objectifs concrets :

```text
1. produire un contrat d'intégration provider complet
2. prouver les comportements critiques sur un vrai compte PAPER
```

Seulement après ce gate, PyTradeKit doit figer :

```text
RuntimeProfile PAPER
AlpacaConfig
AlpacaExecutionAdapter
AlpacaTradeUpdateReceiver
AlpacaSnapshotAdapter
AlpacaMarketDataAdapter
AlpacaCapabilityProvider
```

Le principe à conserver est :

> PyTradeKit doit comprendre Alpaca suffisamment pour l'encapsuler, mais jamais laisser Alpaca définir son modèle de domaine.

---

## 62. Prochaine action recommandée

Créer maintenant le LOT-04 avec un premier sous-lot :

```text
LOT-04A - Alpaca PAPER Probe Harness
```

Le sous-lot doit produire :

```text
scripts/alpaca_paper_probe.py
```

capable, avec credentials fournis uniquement par `SecretsPort` ou variables d'environnement de test, de :

```text
authenticate
get account
get clock
get one asset
get latest quote
get positions
get open orders
connect trade_updates
```

sans encore soumettre d'ordre.

Puis :

```text
LOT-04B - Controlled PAPER Order Probe
```

pour :

```text
MARKET
LIMIT
CANCEL
client_order_id recovery
trade_updates capture
request trace capture
```

Enfin :

```text
LOT-04C - Integration Contract Freeze
```

pour figer les mappings et ouvrir LOT-05.

---

## 63. Références

### Documentation Alpaca

- https://docs.alpaca.markets/us/docs/getting-started
- https://docs.alpaca.markets/us/docs/getting-started-with-trading-api
- https://docs.alpaca.markets/us/docs/paper-trading
- https://docs.alpaca.markets/us/v1.1/docs/authentication-1
- https://docs.alpaca.markets/us/docs/orders-at-alpaca
- https://docs.alpaca.markets/us/docs/working-with-orders
- https://docs.alpaca.markets/us/docs/websocket-streaming
- https://docs.alpaca.markets/us/docs/working-with-account
- https://docs.alpaca.markets/us/docs/working-with-positions
- https://docs.alpaca.markets/us/docs/account-activities
- https://docs.alpaca.markets/us/docs/about-market-data-api
- https://docs.alpaca.markets/us/docs/market-data-faq
- https://docs.alpaca.markets/us/reference/postorder
- https://docs.alpaca.markets/us/reference/stocklatestquotesingle-1
- https://docs.alpaca.markets/us/reference/stockbarsingle-1

### SDK Python

- https://alpaca.markets/sdks/python/api_reference/trading_api.html
- https://alpaca.markets/sdks/python/api_reference/data_api.html
- https://github.com/alpacahq/alpaca-py
- https://github.com/alpacahq/alpaca-py/releases/tag/v0.44.0

### Ancienne documentation archivée

- https://github.com/alpacahq/alpaca-docs

---

## 64. Synthèse finale

Le milestone 0.5 possède maintenant une trajectoire plus sûre :

```text
Persistence first
       |
       v
Provider discovery
       |
       v
Runtime config
       |
       v
Anti-corruption layer
       |
       v
Execution
       |
       v
Market data / snapshots
       |
       v
Startup / recovery baseline
       |
       v
Real PAPER qualification
```

Le point central révélé par cette étude est que l'intégration Alpaca ne doit pas être traitée comme l'ajout d'un simple SDK.

Elle est une frontière de systèmes distribués avec :

```text
remote side effects
network uncertainty
streaming
duplicate delivery
provider-specific state
rate limits
environment separation
credentials
market data entitlements
recovery requirements
```

PyTradeKit doit donc appliquer à Alpaca les mêmes principes déjà établis pour son core :

```text
explicit contracts
canonical identities
idempotency
transactional persistence
bounded side effects
observable state
provider isolation
reconciliation
```

C'est cette discipline qui permet de passer d'un framework de backtest à un runtime PAPER réellement fiable sans sacrifier l'architecture broker-agnostic.