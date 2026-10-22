# 41 - PyTradeKit - IBKR API & SDK Integration Analysis

**Projet :** PyTradeKit  
**Milestone de référence :** `0.5.x - Persistence + Alpaca Paper`  
**Document :** Analyse d'intégration Interactive Brokers API et SDK Python  
**Version :** 1.0  
**Date :** 2026-10-22  
**Statut :** Architecture validation provider - IBKR non ciblé pour implémentation 0.5  
**Périmètre :** TWS API, IB Gateway, Web API, PAPER, ordres, executions, market data, pacing, contrats, connectivité, SDK Python, `ib_async`, sécurité, recovery et implications pour l'architecture provider-agnostic de PyTradeKit

---

## 1. Objet du document

Ce document analyse Interactive Brokers comme troisième provider de référence pour PyTradeKit.

Après Alpaca et Binance Spot, IBKR apporte un modèle d'intégration encore différent :

```text
Alpaca
REST + WebSocket provider hosted

Binance
REST + WebSocket API + Market Streams + User Data Stream

IBKR
TWS API via persistent TCP socket to TWS / IB Gateway
+
Web API REST + WebSocket
```

L'objectif n'est pas d'ajouter IBKR au milestone `0.5.x`.

L'objectif est de tester la robustesse des abstractions actuelles de PyTradeKit face à un provider qui introduit notamment :

```text
persistent local gateway
clientId
nextValidId
orderId sequence
permId
conId
contract qualification
callback-driven state
market-data entitlements
pacing constraints
paper/live port separation
manual and API order interaction
TWS precautionary settings
```

La question centrale est :

> Les abstractions canoniques de PyTradeKit peuvent-elles représenter IBKR sans devenir dépendantes du modèle TWS, de ses IDs, de ses callbacks, de ses sessions ou de ses contraintes de market data ?

---

## 2. Conclusion exécutive

IBKR valide plusieurs choix déjà présents dans PyTradeKit, mais révèle aussi de nouvelles contraintes importantes.

Les concepts suivants restent clairement provider-agnostic :

```text
canonical OrderId
provider client reference
external order id
external fill id
ExecutionCertainty
UNCERTAIN
Inbox
Outbox
UnitOfWork
reconciliation
provider-specific capabilities
provider-specific instrument mapping
Balance
Position
SecretsPort
runtime readiness
```

IBKR ajoute cependant plusieurs enseignements structurants.

### 2.1 Les ordres ont plusieurs identités provider

TWS API distingue notamment :

```text
clientId
orderId
permId
orderRef
execId
```

Cela confirme qu'un seul champ `external_order_id` peut être insuffisant si l'on ne précise pas sa sémantique.

### 2.2 L'instrument doit être résolu par identifiant stable

IBKR recommande fortement :

```text
conId + exchange
```

plutôt qu'une simple résolution par symbole.

Cela valide le besoin de :

```text
ProviderInstrumentMapping
```

### 2.3 La connexion est un composant runtime de premier rang

Avec TWS API :

```text
PyTradeKit
    |
    v
TCP socket
    |
    v
IB Gateway / TWS
    |
    v
IBKR servers
```

Le provider ne se résume donc pas à un client HTTP.

### 2.4 Le callback d'exécution est la vérité économique

Après `placeOrder`, TWS produit notamment :

```text
openOrder
orderStatus
execDetails
error
```

La réponse au call n'est pas une vérité finale.

### 2.5 Le reconnect peut avoir des effets économiques

La configuration TWS expose un paramètre :

```text
maintainAndResubmitOrdersOnReconnect
```

qui peut resoumettre des ordres tentés pendant une perte réseau.

Pour PyTradeKit, cette fonctionnalité doit être explicitement audité et contrôlée.

### 2.6 PAPER n'est pas LIVE-equivalent

IBKR documente plusieurs différences :

```text
simulated fills
top-of-book fill model
unsupported order types
different complex-order behavior
partial directed market order remainder behavior
```

### 2.7 Le market data est entitlement-driven

Les données réelles dépendent :

```text
market data subscriptions
username
market data lines
instrument
exchange
```

### 2.8 Le choix SDK a une dimension licence

Au 2026-10-22 :

```text
TWS API 10.49+
released under GPL according to IBKR changelog
```

Le projet PyTradeKit étant Apache-2.0, une intégration distribuée avec le client officiel `ibapi` nécessite une revue de compatibilité de licence.

Le wrapper communautaire :

```text
ib_async 2.1.0
BSD
```

implémente le protocole TWS sans dépendre de `ibapi`.

Il est donc un candidat technique intéressant, mais il reste non officiel et doit être qualifié comme tel.

---

## 3. Sources de référence

### 3.1 Documentation officielle générale

```text
https://www.interactivebrokers.com/docs/
```

### 3.2 TWS API

```text
https://www.interactivebrokers.com/docs/tws-api/
```

### 3.3 Web API

```text
https://www.interactivebrokers.com/docs/web-api/
```

### 3.4 IBKR Campus

```text
https://www.interactivebrokers.com/campus/ibkr-api-page/ibkr-api-home/
```

### 3.5 Site produit

```text
https://www.interactivebrokers.ie/
https://www.interactivebrokers.com/
```

### 3.6 `ib_async`

```text
https://github.com/ib-api-reloaded/ib_async
```

Version observée :

```text
2.1.0
```

Licence :

```text
BSD
```

### 3.7 Code historique utilisateur

Un client market data historique utilisant :

```text
ib_async
IB
Contract
Forex
Stock
```

a également été analysé.

Il ne contient pas le trading adapter complet.

---

## 4. Familles d'API IBKR

IBKR propose plusieurs surfaces.

```text
IBKR
|
+-- Web API
|
+-- TWS API
|
+-- FIX
|
+-- Excel
|
+-- Third-party integrations
```

Pour PyTradeKit, les deux candidats réalistes sont :

```text
TWS API
Web API
```

FIX est hors scope pour une première intégration.

---

## 5. TWS API

La TWS API est une API socket TCP.

Architecture :

```text
PyTradeKit
    |
    v
TWS API protocol
    |
    v
TWS or IB Gateway
    |
    v
IBKR backend
```

Le client doit donc disposer d'un processus local ou distant :

```text
Trader Workstation
or
IB Gateway
```

La documentation officielle décrit TWS API comme un protocole message-oriented.

---

## 6. Web API

La Web API IBKR utilise :

```text
HTTPS
JSON
WebSocket
OAuth 2.0
```

Elle permet :

```text
trading
market data
portfolio
account
contract search
order monitoring
```

Elle a un modèle de session de brokerage.

Pour certaines opérations `/iserver`, une brokerage session active est obligatoire.

---

## 7. Recommandation PyTradeKit

Pour une future première implémentation IBKR :

```text
TWS API
+
IB Gateway
+
PAPER
```

est le candidat recommandé.

Pourquoi :

```text
existing user experience with ib_async
mature trading surface
strong streaming callbacks
direct order lifecycle visibility
clear PAPER/live port separation
well-documented execution callbacks
multi-asset support
```

IB Gateway est préférable à TWS pour un runtime automatisé car il est plus léger et n'impose pas l'UI complète.

---

## 8. Web API reste importante

La Web API ne doit pas être ignorée.

Elle est intéressante pour :

```text
REST-native deployment
hosted integration
OAuth 2.0
websocket topics
simpler container-facing HTTP boundary
```

Mais elle possède des contraintes différentes :

```text
brokerage session
OAuth registration
reply confirmations
HTTP 200 with business rejection
session-specific market data
```

Elle mérite une future analyse dédiée si PyTradeKit veut supporter deux transports IBKR.

---

## 9. TWS API version

La documentation IBKR indique :

```text
TWS API 10.49 released on 2026-08-03
```

Le changelog continue d'être mis à jour en octobre 2026.

Cela signifie qu'une intégration doit être version-aware.

---

## 10. Sync Wrapper officiel

Depuis TWS API 10.40, IBKR fournit une API Python synchrone :

```python
from ibapi.sync_wrapper import TWSSyncWrapper
```

Elle permet d'obtenir directement les retours de certaines opérations au lieu de manipuler uniquement :

```text
EClient
EWrapper
EReader
```

Cela rapproche l'expérience du modèle de `ib_async`.

---

## 11. SDK officiel vs `ib_async`

### SDK officiel

```text
ibapi
official
TWS API 10.49+
current release licensing requires review
```

### ib_async

```text
community maintained
BSD
Python >= 3.10
version 2.1.0 observed
implements TWS binary protocol directly
does not require ibapi
sync + async
```

---

## 12. Gate de licence

Le changelog actuel indique :

```text
TWS API 10.49+ is released under GPL
```

Une page d'architecture conserve encore une formulation historique décrivant la TWS API comme une :

```text
BSD implementation
```

Ces deux formulations ne doivent pas être ignorées.

Pour PyTradeKit :

```text
Apache-2.0 project
```

la règle doit être :

```text
do not bundle official ibapi 10.49+
until license compatibility is explicitly reviewed
```

Ce document n'est pas un avis juridique.

---

## 13. Option `ib_async`

`ib_async` est BSD-2-Clause et ne dépend pas d'`ibapi`.

Cela réduit la contrainte de distribution côté PyTradeKit.

Mais :

```text
non-official implementation
```

signifie qu'il faut :

```text
pin version
contract test
protocol compatibility qualification
Gateway regression tests
upgrade policy
```

---

## 14. Architecture provider cible

```text
                       PyTradeKit Domain
                              |
                              v
                      Application Ports
                              |
               +--------------+--------------+
               |                             |
               v                             v
        ExecutionPort                 MarketDataPort
               |                             |
               +--------------+--------------+
                              |
                              v
                         IBKR ACL
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
       Order transport   Private events   Market data
              |               |               |
              +---------------+---------------+
                              |
                              v
                    ib_async / TWS protocol
                              |
                              v
                       IB Gateway PAPER
```

---

## 15. IB Gateway vs TWS

IBKR exige l'un des deux pour TWS API.

### TWS

```text
full trading UI
useful for manual inspection
more resource intensive
```

### IB Gateway

```text
lighter
headless-oriented
same API surface
better runtime candidate
```

Pour production-like automation :

```text
IB Gateway
```

est préférable.

---

## 16. PAPER vs LIVE ports

Default ports officiels :

```text
TWS LIVE
7496

TWS PAPER
7497

IB Gateway LIVE
4001

IB Gateway PAPER
4002
```

Ces valeurs sont critiques.

---

## 17. PAPER hard-lock

Une future implémentation PyTradeKit doit refuser :

```text
7496
4001
```

dans un runtime déclaré PAPER.

Cible :

```text
IBKREnvironment.PAPER
```

doit autoriser uniquement :

```text
7497
4002
```

sauf explicit override de test fortement contrôlé.

---

## 18. Pas de fallback LIVE

Jamais :

```text
port missing
=> 4001
```

ou :

```text
port missing
=> 7496
```

Le runtime doit échouer.

---

## 19. Connection handshake

TWS API ne devient pas opérationnelle dès l'ouverture TCP.

Il existe une handshake.

La documentation indique que TWS retourne notamment :

```text
accounts
next valid order ID
connection time
```

---

## 20. nextValidId comme readiness gate

La documentation recommande d'utiliser :

```text
nextValidID
```

comme signal qu'une connexion est réellement initialisée.

Des appels envoyés avant peuvent être perdus.

Donc :

```text
socket connected
!=
provider ready
```

---

## 21. Readiness TWS proposée

```text
TCP connected
AND
protocol version negotiated
AND
nextValidId received
AND
account verified
AND
PAPER port verified
AND
contract services responsive
AND
required market data permissions known
AND
reconciliation completed
```

---

## 22. clientId

TWS supporte plusieurs API clients simultanés.

La documentation mentionne jusqu'à :

```text
32 API connections
```

Le `clientId` différencie les connexions.

---

## 23. clientId n'est pas un simple correlation ID

Le `clientId` a des conséquences sur :

```text
order ownership
order modification
order cancellation
open order binding
```

Un ordre n'est pas librement modifiable depuis n'importe quel client.

---

## 24. clientId 0

IBKR recommande `clientId=0` pour certaines fonctions d'order management optimales.

En particulier :

```text
manual TWS orders
binding
auto open orders
```

peuvent dépendre du client 0.

---

## 25. Stratégie PyTradeKit clientId

Une première intégration doit choisir une policy explicite.

Option :

```text
execution client
clientId = 1

market data client
clientId = 2
```

correspond à l'approche historique utilisateur.

Avantage :

```text
separation of concerns
```

Inconvénient :

```text
order ownership and recovery complexity
```

---

## 26. Alternative recommandée

Pour le premier vertical slice :

```text
one dedicated execution connection
+
optional dedicated readonly market connection
```

mais toutes les opérations liées à un ordre doivent rester sur le même clientId logique.

---

## 27. orderId

`orderId` est l'identifiant API client de l'ordre.

Il est séquencé.

Règle :

```text
new orderId
must be greater than prior IDs used by the client
```

Un duplicate ou lower ID provoque une erreur.

---

## 28. nextValidId

TWS expose le prochain ID valide.

Cet ID doit être traité comme :

```text
provider sequencing state
```

et non comme :

```text
PyTradeKit OrderId
```

---

## 29. Concurrency implication

Si plusieurs producers soumettent des ordres via une même session :

```text
orderId allocation
```

doit être sérialisée.

Cela nécessite :

```text
single allocator
lock
or
single execution actor
```

---

## 30. orderRef

IBKR possède également :

```text
orderRef
```

Le champ est user-customizable et associé à l'ordre pendant son cycle de vie.

Cela fournit une primitive beaucoup plus proche de :

```text
client_order_id
newClientOrderId
```

que `orderId`.

---

## 31. Limite orderRef

La documentation TWS le décrit historiquement comme destiné aux clients institutionnels.

Il ne faut donc pas supposer sans probe qu'il se comporte exactement comme :

```text
Alpaca client_order_id
Binance newClientOrderId
```

---

## 32. Web API cOID

La Web API possède :

```text
cOID
```

comme client-configurable order identifier.

La documentation indique une unicité sur 24 heures et une longueur maximale de 64 caractères.

Cela est beaucoup plus proche du canonical client order reference.

---

## 33. Provider client reference abstraction

Après Alpaca, Binance et IBKR, le modèle doit distinguer :

```text
canonical OrderId

provider_client_reference

provider_session_order_id

provider_permanent_order_id
```

---

## 34. Mapping IBKR proposé

```text
PyTradeKit OrderId
        |
        +-- orderRef or cOID
        |
        +-- orderId
        |
        +-- permId
```

Avec sémantiques différentes.

---

## 35. permId

`permId` est un identifiant host IBKR.

La documentation précise qu'il peut identifier l'ordre de manière unique dans le compte.

Il est plus stable que :

```text
orderId
```

dans les scénarios multi-session.

---

## 36. external order identity

Future structure possible :

```text
ProviderOrderIdentity
    provider
    client_reference
    session_order_id
    permanent_order_id
```

Exemple IBKR :

```text
client_reference = orderRef
session_order_id = orderId
permanent_order_id = permId
```

---

## 37. execId

Chaque exécution IBKR possède :
```text
execId
```

Chaque partial fill reçoit son propre `execId`.

Cela en fait une très bonne candidate pour :

```text
external_fill_id
```

---

## 38. Execution correction

IBKR indique qu'une correction d'exécution peut produire un `execId` proche du précédent, différant après le dernier point.

Cela signifie que :

```text
fill immutable forever
```

n'est pas toujours une hypothèse suffisante.

---

## 39. Future correction model

PyTradeKit pourra avoir besoin plus tard de :

```text
ExecutionCorrection
```

ou :

```text
FillAdjustment
```

Mais ce concept ne doit pas être ajouté à 0.5 sans besoin réel.

---

## 40. placeOrder

TWS API soumet via :

```text
EClient.placeOrder
```

Après soumission correcte, TWS produit des callbacks :

```text
openOrder
orderStatus
```

et les executions via :

```text
execDetails
```

---

## 41. Command ACK vs fact

Comme Alpaca et Binance :

```text
command submission
!=
economic fact
```

Architecture :

```text
placeOrder
    |
    v
command transport
    |
    v
openOrder / orderStatus
    |
    v
execDetails
```

---

## 42. Private event receiver

Future component :

```text
IBKROrderEventReceiver
```

qui normalise :

```text
openOrder
orderStatus
execDetails
error
commissionAndFeesReport
```

---

## 43. Inbox integration

Flow :

```text
IB callback
    |
    v
provider event identity
    |
    v
Inbox.claim
    |
    +-- duplicate -> stop
    |
    v
map canonical fact
    |
    v
OMS / Portfolio
    |
    v
Outbox
    |
    v
COMMIT
```

---

## 44. Order state callbacks

Le runtime doit écouter au minimum :

```text
openOrder
orderStatus
execDetails
error
```

IBKR recommande explicitement de surveiller ces callbacks pour diagnostiquer correctement les ordres.

---

## 45. Status model

IBKR utilise des états tels que :

```text
PendingSubmit
PendingCancel
PreSubmitted
Submitted
ApiCancelled
Cancelled
Filled
Inactive
```

Le mapping ne doit pas recopier ces strings directement dans le Domain.

---

## 46. Example mapping

Conceptuel :

```text
PendingSubmit
-> SUBMITTED

PreSubmitted
-> ACCEPTED / HELD

Submitted
-> ACCEPTED

PendingCancel
-> CANCEL_REQUESTED

ApiCancelled
-> CANCELED

Cancelled
-> CANCELED

Filled
-> FILLED

Inactive
-> REJECTED / INACTIVE depending reason
```

Le mapping final doit être validé par PAPER fixtures.

---

## 47. `whyHeld`

L'order status peut inclure :

```text
whyHeld
```

Cela montre qu'un ordre peut être accepté mais retenu.

PyTradeKit doit distinguer :

```text
accepted
```

de :

```text
actively working
```

si cette nuance devient nécessaire.

---

## 48. Order precautionary settings

TWS peut bloquer ou retenir des ordres selon des paramètres de précaution configurés.

Une erreur peut donc provenir :

```text
TWS local settings
```

et non uniquement :

```text
IBKR server
exchange
```

---

## 49. Web API reply confirmation

Web API rend cette notion encore plus explicite.

Un order submit peut retourner :

```text
reply message
```

qui exige un second call de confirmation.

Donc :

```text
HTTP success
!=
order transmitted
```

---

## 50. Business rejection with HTTP 200

La Web API peut retourner :

```text
HTTP 200
```

avec :

```text
{"error": "..."}
```

pour certains order rejects.

Cela confirme que le mapping ne peut jamais dépendre uniquement du status HTTP.

---

## 51. No second order before reply resolution

IBKR recommande de ne pas placer un autre ordre avant résolution complète d'un reply warning.

Cela signifie qu'une command pipeline Web API devrait être séquentielle sur ce point.

---

## 52. TWS reconnect risk

IBKR expose une option de configuration :

```text
maintainAndResubmitOrdersOnReconnect
```

dont la sémantique est :

```text
submit orders that attempted transmission while disconnected
```

C'est un point critique.

---

## 53. PyTradeKit rule

Le runtime doit interdire toute resoumission implicite non contrôlée.

Principe :

```text
disconnect during submit
        |
        v
UNCERTAIN
        |
        v
reconcile
```

et non :

```text
disconnect
        |
        v
automatic resubmit
```

---

## 54. Gate configuration

Avant toute intégration TWS :

```text
[ ] maintainAndResubmitOrdersOnReconnect behavior verified
[ ] automatic resubmit disabled or safely bounded
[ ] unknown order outcomes persisted
[ ] reconnect reconciliation implemented
```

---

## 55. Connectivity errors

IBKR possède de nombreux codes connectivity.

Exemples structurants :

```text
501 already connected
502 cannot connect
503 TWS out of date
504 not connected
```

et plusieurs codes système autour de perte/restauration de connectivité.

---

## 56. Connection state model

Future runtime :

```text
DISCONNECTED
CONNECTING
HANDSHAKING
READY
DEGRADED
RECONCILING
```

---

## 57. Socket reconnect != readiness

Un socket reconnecté doit encore :

```text
complete handshake
verify account
recover order state
recover subscriptions
```

avant de repasser READY.

---

## 58. Restart recovery

Au restart :

```text
local unresolved orders
        |
        v
connect Gateway
        |
        v
handshake
        |
        v
request open orders
        |
        v
request executions
        |
        v
map by orderRef/orderId/permId
        |
        v
converge
```

---

## 59. Order binding complexity

IBKR permet de lier certains ordres existants à un API client.

Le binding peut être requis pour :

```text
manual TWS orders
orders from another session
```

---

## 60. Queue priority risk

IBKR documente que binding peut impliquer :

```text
cancel / resubmit at exchange
```

et donc affecter :

```text
queue priority
```

C'est une conséquence économique réelle.

---

## 61. Scope first implementation

Pour le premier adapter IBKR futur :

```text
manage only orders created by PyTradeKit
```

Hors scope initial :

```text
adopt arbitrary manual TWS orders
modify arbitrary external orders
bind external sessions
```

Cela simplifie fortement la recovery.

---

## 62. Instrument identity

IBKR recommande :

```text
conId
+
exchange
```

comme définition stable.

---

## 63. conId

Le `conId` identifie un instrument chez IBKR.

Il est beaucoup plus fiable qu'un symbole.

Exemple :

```text
AAPL
```

seul ne suffit pas toujours.

---

## 64. Contract definition

Une Contract peut nécessiter :

```text
symbol
secType
exchange
currency
primaryExchange
expiry
strike
right
multiplier
localSymbol
tradingClass
```

selon l'instrument.

---

## 65. Contract qualification

Un future adapter doit faire :

```text
canonical InstrumentId
        |
        v
ProviderInstrumentMapping
        |
        v
qualified IBKR Contract
        |
        v
conId
```

---

## 66. Avoid symbol heuristics

Ne pas faire en production :

```text
if len(symbol) == 6:
    Forex
else:
    Stock
```

Le mapping doit être explicite.

---

## 67. Multi-asset richness

IBKR supporte notamment :

```text
stocks
ETFs
forex
futures
options
bonds
CFDs
funds
combos
event contracts
```

Cela en fait un excellent test de l'Instrument model.

---

## 68. Scope initial IBKR

Pour une première intégration :

```text
US EQUITY
```

ou éventuellement :

```text
US EQUITY + ETF
```

Pas tout le catalogue.

---

## 69. ContractDetails

IBKR expose :

```text
minTick
orderTypes
validExchanges
marketRuleIds
minSize
sizeIncrement
suggestedSizeIncrement
```

Cela valide encore le besoin :

```text
InstrumentTradingConstraints
```

---

## 70. Market rules

`minTick` ne suffit pas toujours.

Le minimum price increment peut changer selon :

```text
price level
exchange
```

IBKR fournit :

```text
reqMarketRule
```

pour les structures complètes.

---

## 71. Convergence avec Binance

Binance :

```text
PRICE_FILTER
LOT_SIZE
MIN_NOTIONAL
```

IBKR :

```text
minTick
marketRuleIds
minSize
sizeIncrement
validExchanges
```

Conclusion :

```text
InstrumentTradingConstraints
```

est réellement provider-agnostic.

---

## 72. SMART routing

IBKR permet :

```text
exchange = SMART
```

Le provider peut router dynamiquement vers plusieurs venues.

Cela signifie que :

```text
requested venue
```

et :

```text
execution venue
```

peuvent différer.

---

## 73. Execution exchange

`Execution.exchange` indique où l'exécution a réellement eu lieu.

PyTradeKit doit pouvoir conserver :

```text
execution_venue
```

comme metadata de Fill.

---

## 74. Account identity

Une connexion TWS est liée à un username qui peut avoir accès à plusieurs comptes.

Le startup doit vérifier :

```text
expected account
```

avant READY.

---

## 75. Username vs account

Comme avec Web API :

```text
permissions may belong to username
```

et les assets/funds appartiennent au compte.

Le runtime doit distinguer :

```text
session identity
account identity
```

---

## 76. Account scope

Première intégration :

```text
one explicit account
```

Hors scope initial :

```text
advisor allocations
linked accounts
models
omnibus
multi-account routing
```

---

## 77. PAPER account

IBKR Paper Trading permet de tester des stratégies sans risque financier.

Mais la simulation n'est pas identique au Live.

---

## 78. PAPER limitations

IBKR documente notamment :

```text
fills simulated from top of book
no deep book execution model
limited combos and EFP
some order types unsupported
stops and complex orders simulated
penny fills on US options unsupported
directed market partial remainder behavior differs
mutual funds unsupported
```

---

## 79. PAPER qualification meaning

```text
PAPER qualified
!=
LIVE execution equivalent
```

Même principe qu'Alpaca.

---

## 80. PAPER market data

Un paper account peut dépendre des subscriptions du live account.

Sans subscription :

```text
US stocks delayed 15 min
US options delayed 15 min
US futures delayed 10 min
```

avec d'autres classes pouvant être non retardées selon IBKR.

---

## 81. Readiness market data

Le runtime doit savoir :

```text
REALTIME
DELAYED
FROZEN
DELAYED_FROZEN
UNAVAILABLE
```

et non seulement :

```text
market_data = yes
```

---

## 82. Market data entitlements

Les données dépendent de :

```text
username
subscriptions
exchange
instrument
```

Donc :

```text
capability
```

doit être observée dynamiquement.

---

## 83. Market data lines

IBKR limite le nombre de streams simultanés via :

```text
market data lines
```

Ces lignes sont partagées entre :

```text
TWS watchlists
API connections
```

---

## 84. Runtime implication

Deux processes PyTradeKit peuvent se concurrencer indirectement sur les mêmes market data lines.

Il faut donc observer :

```text
subscription count
rejection code
available capacity
```

---

## 85. Message pacing

IBKR documente des limites de messages API.

Le code d'erreur 100 mentionne encore :

```text
50 messages / second
```

et le changelog 2025 indique que certaines limites modernes sont désormais liées aux market data lines.

Le runtime ne doit donc pas hardcoder une valeur universelle sans capability/version context.

---

## 86. Historical pacing

Pour petites bars, IBKR documente notamment :

```text
no identical request within 15 seconds
< 6 requests same contract/exchange/tick type in 2 seconds
<= 60 requests in 10 minutes
```

---

## 87. Historical data is filtered

IBKR précise que l'historique peut être :

```text
filtered
adjusted
compressed
```

et ne pas correspondre exactement aux données temps réel.

Cela est critique pour backtesting.

---

## 88. Backtest source semantics

PyTradeKit doit conserver :

```text
data_source
adjustment
whatToShow
useRTH
exchange
timezone
```

dans les metadata de dataset.

---

## 89. TRADES vs MIDPOINT

IBKR permet différents `whatToShow`.

Exemples :

```text
TRADES
MIDPOINT
BID
ASK
BID_ASK
```

Une Bar n'a donc pas toujours la même signification économique.

---

## 90. Market data adapter split

Architecture future :

```text
IBKRHistoricalMarketDataAdapter
IBKRRealtimeMarketDataAdapter
IBKRMarketRuleAdapter
```

Ne pas créer un gigantesque `IBKRClient`.
---

## 91. Tick update frequency

IBKR documente des fréquences différentes par produit.

Exemples :

```text
US stocks 250ms
US options 100ms
Forex 5ms
```

Cela doit être représenté comme qualité de source, pas comme promesse universelle.

---

## 92. Tick-by-tick limitations

Tick-by-tick n'est pas disponible pour tous les produits.

Il est aussi soumis à des limitations de subscriptions.

Conclusion :

```text
REALTIME_MARKET_DATA
```

est une capability trop grossière.

---

## 93. Live market data subscriptions

La plupart des instruments nécessitent des abonnements payants.

Cela signifie :

```text
provider connected
!=
market data available
```

---

## 94. Market data health

Future state :

```text
CONNECTED_REALTIME
CONNECTED_DELAYED
ENTITLEMENT_MISSING
PACING_LIMITED
DISCONNECTED
```

---

## 95. Web API market data

Web API expose également market data via HTTP et WebSocket.

Le changelog 2026 note notamment :

```text
historical market data pacing
10 requests/sec
50 requests/min
```

et certaines subscriptions WebSocket SMD doivent être renouvelées après 10 minutes.

---

## 96. Transport-specific capabilities

Cela montre que même au sein d'IBKR :

```text
TWS API
Web API
```

peuvent avoir des contraintes différentes.

Le provider model doit inclure :

```text
transport
```

dans le capability context.

---

## 97. Order types

IBKR supporte plus de 100 order types, algos et tools.

PyTradeKit ne doit pas essayer de les normaliser tous.

---

## 98. Scope initial future

```text
MARKET
LIMIT
CANCEL
QUERY
```

comme Alpaca et Binance.

---

## 99. Extended / overnight trading

IBKR possède des notions :

```text
outsideRth
OVERNIGHT
OVERNIGHT+DAY
```

Elles doivent rester capability/provider-specific au départ.

---

## 100. Simulated order types

Certains order types sont simulés par IBKR et non natifs à l'exchange.

Cela démontre qu'une capability doit potentiellement distinguer :

```text
NATIVE
BROKER_SIMULATED
PAPER_SIMULATED
```

---

## 101. Execution provenance

Future metadata :

```text
ProviderExecutionMetadata
    exchange
    liquidity
    submitter
    liquidation
    pending_price_revision
```

Pas nécessairement dans le Domain core.

---

## 102. Commission and fees

IBKR fournit :

```text
CommissionAndFeesReport
```

lié à :

```text
execId
```

avec :

```text
commissionAndFees
currency
realizedPNL
```

---

## 103. Fill + fee timing

L'exécution et les fees peuvent arriver via des événements distincts.

Donc :

```text
Fill
```

peut être créé avant que :

```text
final commission/fee
```

soit connue.

---

## 104. Future fee enrichment

Un modèle éventuel :

```text
Fill
+
ExecutionFeeUpdate
```

peut être plus réaliste qu'un Fill exigeant toujours tous les coûts immédiatement.

À ne pas ajouter à 0.5 sans nécessité.

---

## 105. Decimal policy

L'API IBKR historique utilise plusieurs `double`.

Le SDK moderne a progressivement introduit des Decimal sur certains champs.

PyTradeKit doit convertir systématiquement :

```text
price
quantity
commission
cash
position
```

vers :

```text
Decimal
```

au boundary.

---

## 106. Time semantics

IBKR peut retourner des timestamps dans :

```text
exchange timezone
operator timezone
UTC
```

selon configuration.

La normalisation timezone doit être explicite.

---

## 107. Provider timezone config

La configuration API TWS expose des paramètres permettant d'envoyer l'historique selon :

```text
instrument
operator
utc
```

PyTradeKit doit préférer :

```text
UTC
```

lorsque possible.

---

## 108. Audit du client historique - bon point

Le client fourni utilise :

```python
Decimal(str(...))
```

pour :

```text
open
high
low
close
volume
```

C'est correct pour PyTradeKit.

---

## 109. Audit du client historique - bug timezone

Le code reçoit par exemple :

```text
20240109 09:30:00 US/Eastern
```

puis retire le timezone et fait :

```python
dt.replace(tzinfo=timezone.utc)
```

Le commentaire indique explicitement :

```text
treat as UTC for simplicity
```

Ce comportement est incorrect pour un runtime trading.

---

## 110. Impact du bug timezone

Exemple :

```text
09:30 US/Eastern
```

ne signifie pas :

```text
09:30 UTC
```

Cela peut décaler :

```text
bars
signals
market open
backtest alignment
```

de plusieurs heures.

---

## 111. Correctif futur

Utiliser :

```text
zoneinfo
```

et la timezone fournie par IBKR.

Ou configurer IBKR pour retourner directement UTC lorsque possible.

---

## 112. Audit du client historique - close_time

Le code fixe :

```text
close_time = open_time
```

pour les bars.

Cela peut être acceptable comme placeholder mais ne doit pas être présenté comme une vraie close time.

---

## 113. Audit du client historique - average mapping

Le code mappe :

```text
bar.average
```

vers :

```text
quote_asset_volume
```

alors que le commentaire le décrit comme :

```text
VWAP-like
```

Ces sémantiques ne sont pas équivalentes.

Le mapping doit être corrigé.

---

## 114. Audit du client historique - symbol heuristic

Le resolver historique fait :

```text
contains /
-> Forex

6 uppercase letters
-> Forex

otherwise
-> Stock SMART USD
```

Cette heuristic est trop fragile.

---

## 115. Problem examples

```text
EURUSD
AAPL
BRK B
RDSA
futures
options
crypto
European stocks
non-USD stocks
```

ne peuvent pas être correctement résolus par une simple règle de longueur.

---

## 116. Contract qualification correct model

```text
canonical instrument
        |
        v
provider mapping
        |
        v
Contract
        |
        v
qualify
        |
        v
conId
```

---

## 117. Audit du client historique - crypto claim

Le docstring indique support :

```text
stocks
forex
crypto with correct contract
```

mais `_resolve_contract` ne construit que :

```text
Forex
Stock
```

Le support crypto n'est donc pas réellement implémenté dans cette heuristic.

---

## 118. Audit du client historique - market client read-only

Le code connecte :

```text
readonly=True
```

pour le market data client.

C'est une bonne séparation.

---

## 119. Audit du client historique - distinct clientId

Le market client utilise par défaut :

```text
client_id = 2
```

afin d'éviter le trading adapter.

C'est cohérent avec la séparation fonctionnelle, mais les implications de récupération d'ordres imposent une policy plus formelle.

---

## 120. Audit du client historique - static symbol list

`get_available_symbols()` retourne une liste statique.

Cela montre que :

```text
IBKR is not a symbol-directory API
```

et renforce le besoin d'un vrai registry d'instruments.

---

## 121. Static list should not enter PyTradeKit core

Un adapter ne doit pas présenter une liste hardcodée comme :

```text
provider universe
```

Il doit supporter :

```text
resolve known mapping
search provider contracts
qualify contract
```

---

## 122. Execution certainty

IBKR ne documente pas un `-1007 UNKNOWN` comme Binance, mais le modèle réseau reste distribué.

Scénario :

```text
placeOrder
    |
    v
socket breaks
    |
    ?
```

Le caller peut ne pas savoir immédiatement si TWS/IBKR a accepté.

---

## 123. Unknown submit policy

PyTradeKit doit donc appliquer :

```text
transport error after send
=> UNCERTAIN
```

jusqu'à reconciliation.

---

## 124. Recovery identity

Pour retrouver l'ordre :

```text
orderRef
orderId
permId
open orders
completed orders
executions
```

peuvent contribuer.

---

## 125. Strong recovery key

Une fois attribué :

```text
permId
```

est une identité provider forte.

Avant attribution :

```text
orderRef
+
clientId
+
orderId
```

peut être nécessaire.

---

## 126. Persistence implication

La table broker mappings devrait pouvoir représenter plusieurs IDs provider.

Un modèle clé/valeur typé peut être préférable à :

```text
one external_order_id column
```

à long terme.

---

## 127. Provider order mapping candidate

```text
ProviderOrderMapping
    provider
    canonical_order_id
    client_reference
    session_order_id
    permanent_order_id
    session_id
    account_id
    first_seen_at
```

---

## 128. Client ID persistence

Pour IBKR, persister :

```text
clientId
```

avec l'ordre peut aider recovery et cancel/modify.

---

## 129. Session-aware cancellation

IBKR indique que cancel/modify d'un ordre API dépend du clientId auquel il est bound.

La cancellation n'est donc pas seulement :

```text
external_order_id
```

---

## 130. Cancel command model

Future adapter :

```text
cancel(canonical_order_id)
```

doit résoudre :

```text
clientId
orderId
permId
```

en infrastructure.

Le Domain ne doit pas les connaître.

---

## 131. Cancel-fill race

Comme les autres providers :

```text
cancel requested
        |
        +---------+
        |         |
        v         v
cancelled       fill
```

L'OMS actuel reste pertinent.

---

## 132. Order modification

IBKR permet de rappeler `placeOrder` avec le même orderId pour modifier.

Mais modifier depuis une autre session peut nécessiter binding.

---

## 133. Queue priority

Certaines modifications/bindings peuvent affecter la priorité exchange.

Cela montre que :

```text
modify order
```

n'est pas économiquement neutre.

Hors premier scope.

---

## 134. Manual orders

IBKR est particulièrement intéressant car :

```text
manual TWS orders
```

et :

```text
API orders
```

peuvent coexister.

Une future integration devra choisir :

```text
PyTradeKit-owned only
```

ou :

```text
account-wide reconciliation
```

---

## 135. Recommended initial ownership model

```text
PyTradeKit manages only PyTradeKit-originated orders
```

détectés via :

```text
orderRef
and local mappings
```

---

## 136. Account-wide visibility

Le runtime peut néanmoins observer les positions et balances account-wide.

Cela signifie :

```text
orders ownership
```

et :

```text
portfolio ownership
```

sont des concepts différents.

---

## 137. External activity

Des positions peuvent changer via :

```text
manual order
other API client
corporate action
IB liquidation
```

Le Portfolio doit donc être reconciliable avec le provider.

---

## 138. Position snapshot

IBKR fournit des positions.

Cela correspond naturellement à :

```text
PositionRepository
ProviderPositionSnapshot
```

---

## 139. Account values

IBKR fournit :

```text
cash
net liquidation
buying power
margin values
P&L
```

Ces metrics ne doivent pas être forcées dans un simple Balance.

---

## 140. Account snapshot

Future structure :

```text
BrokerAccountSnapshot
    account_id
    cash_by_currency
    net_liquidation
    buying_power
    margin
    observed_at
```

avec champs optionnels provider-specific.

---

## 141. Multi-currency

IBKR peut gérer plusieurs currencies dans le même compte.

Cela confirme que :

```text
Balance
```

doit être currency-aware.

---

## 142. Market data and account permissions

Une session peut être autorisée à trader un instrument sans disposer du market data temps réel correspondant.

Donc :

```text
execution capability
```

et :

```text
market data capability
```

doivent être indépendantes.

---

## 143. Capability model IBKR

Exemples :

```text
MARKET_ORDER
LIMIT_ORDER
CANCEL
ORDER_QUERY
POSITION_QUERY
ACCOUNT_QUERY
REALTIME_QUOTES
DELAYED_QUOTES
HISTORICAL_BARS
TICK_BY_TICK
MARKET_DEPTH
```

---

## 144. Capability context

```text
provider = IBKR
transport = TWS
environment = PAPER
account
instrument
exchange
market_data_subscription
```

---

## 145. Market data quality

Un même request peut retourner :

```text
live
delayed
frozen
```

Le type de feed doit être attaché à l'observation.

---

## 146. Instrument constraints

Après Binance et IBKR, le contract canonique devient encore plus justifié.

```text
InstrumentTradingConstraints
    min_price_increment
    min_size
    size_increment
    valid_order_types
    valid_venues
    observed_at
```

---

## 147. Dynamic tick size

IBKR montre que :

```text
minTick
```

peut être price-dependent.

Donc un simple :

```text
tick_size: Decimal
```

peut être insuffisant.

---

## 148. Price increment schedule

Future representation possible :

```text
PriceIncrementRule
    low_edge
    increment
```

comme provider-derived constraint.
---

## 149. Venue routing

Pour IBKR :

```text
SMART
```

peut router vers plusieurs exchanges.

PyTradeKit devrait distinguer :

```text
routing instruction
```

de :

```text
execution venue
```

---

## 150. Market data venue

Une demande SMART et une demande directed peuvent produire des différences.

Les metadata de source doivent conserver :

```text
exchange
primaryExchange
whatToShow
```

---

## 151. PAPER account startup

Future startup :

```text
01 load profile
02 require PAPER
03 verify allowed port
04 connect IB Gateway
05 complete handshake
06 receive nextValidId
07 verify expected account
08 load local unresolved orders
09 request open/completed orders
10 request executions
11 reconcile
12 qualify required contracts
13 load market rules
14 verify market data entitlements
15 subscribe private/order callbacks
16 start required market streams
17 expose READY
```

---

## 152. Readiness must be conservative

Ne pas exposer READY si :

```text
socket connected
but
handshake incomplete
```

ou :

```text
account mismatch
```

ou :

```text
reconciliation unresolved beyond policy
```

---

## 153. Gateway process supervision

TWS API ajoute une nouvelle responsabilité :

```text
IB Gateway process
```

Le runtime doit savoir si :

```text
process alive
port open
API connected
backend connected
```

---

## 154. Containerization

Une future version Docker devra traiter :

```text
Gateway lifecycle
authentication
2FA/session constraints
GUI/headless needs
persistent settings
networking
```

Cela est plus complexe qu'Alpaca/Binance.

---

## 155. Secrets model

TWS API ne transmet pas directement les credentials dans chaque API call.

L'authentification se fait au niveau :

```text
TWS / Gateway login
```

Cela modifie la façon dont SecretsPort est utilisé.

---

## 156. Secrets candidates

```text
IBKR_USERNAME
IBKR_PASSWORD
2FA/session material
gateway config
```

doivent rester hors config visible.

---

## 157. No credential logging

Même principe :

```text
no username/password/token
no account ID unless redacted according to policy
```

---

## 158. Account identifiers

Les account IDs peuvent être considérés sensibles dans logs externes.

Préférer :

```text
hash
internal alias
```

dans observabilité publique.

---

## 159. Web API OAuth 2.0

La Web API officielle utilise :

```text
OAuth 2.0
private_key_jwt
```

Cela est plus proche d'une intégration SaaS.

---

## 160. Web API session restriction

Une brokerage session est nécessaire pour :

```text
market data
place orders
iserver endpoints
```

Un username ne peut avoir qu'une session brokerage active à la fois selon la documentation.

---

## 161. Runtime implication Web API

Un futur Web API adapter doit modéliser :

```text
oauth auth
brokerage session auth
websocket session
account selection
```

séparément.

---

## 162. Web API order updates

WebSocket topic :

```text
sor
```

pour order updates.

Topic :

```text
str
```

pour trades.

Cela mappe naturellement vers les mêmes canonical facts que TWS callbacks.

---

## 163. Transport abstraction opportunity

IBKR pourrait fournir deux implementations du même port :

```text
IBKRTWSExecutionAdapter
IBKRWebExecutionAdapter
```

Le Domain resterait inchangé.

---

## 164. Do not unify transports prematurely

Les contraintes diffèrent trop pour masquer toutes les différences derrière une classe unique au début.

Préférer :

```text
shared mappers where semantics match
+
transport-specific infrastructure
```

---

## 165. Web API cOID

La Web API rend `cOID` très utile pour recovery.

Future comparison :

```text
Alpaca client_order_id
Binance newClientOrderId
IBKR Web cOID
IBKR TWS orderRef
```

---

## 166. Canonical ClientOrderReference

Ces quatre providers/surfaces justifient fortement :

```text
ClientOrderReference
```

comme concept application/persistence.

---

## 167. But not all references have identical guarantees

Il faut stocker :

```text
provider
reference value
scope
uniqueness semantics
```

et ne pas supposer :

```text
global lifetime uniqueness
```

---

## 168. External permanent identity

IBKR `permId` est une nouvelle catégorie d'identité.

PyTradeKit devra peut-être distinguer :

```text
provider_client_reference
provider_order_id
provider_permanent_id
```

---

## 169. Execution identity

`execId` constitue une identité fill-level très forte.

Inbox key candidate :

```text
IBKR:EXEC:{execId}
```

---

## 170. Commission identity

`CommissionAndFeesReport.execId` permet de relier les fees à l'execution.

Très bon candidat pour :

```text
execution enrichment
```

---

## 171. Reconciliation sources

TWS future reconciliation peut utiliser :

```text
open orders
completed orders
executions
positions
account values
```

---

## 172. Reconciliation layering

```text
Order reconciliation
Execution reconciliation
Portfolio reconciliation
Account reconciliation
```

Ne pas tout fusionner dans une seule procédure opaque.

---

## 173. Provider truth hierarchy

Pour un ordre :

```text
execution
>
order status
>
open order cache
>
local assumption
```

selon le contexte.

Le design final doit documenter cette hiérarchie.

---

## 174. Completed orders

Un ordre n'étant plus open doit rester retrouvable via l'historique provider lorsque possible.

Cela est nécessaire pour restart recovery.

---

## 175. Connection loss during market data

Les subscriptions doivent être rétablies après reconnect selon le comportement du client/SDK.

Mais :

```text
resubscribe market data
```

n'est pas :

```text
reconcile orders
```

---

## 176. Connection loss during submit

C'est le scénario critique.

```text
local sends placeOrder
        |
        X connection lost
        |
        v
UNKNOWN
```

Policy :

```text
do not generate new orderId and resubmit blindly
```

---

## 177. Recovery approach

```text
persist orderRef before send
persist allocated orderId before send
        |
        v
submit
        |
        X
        |
        v
UNCERTAIN
        |
        v
reconnect
        |
        v
query open/completed orders + executions
        |
        v
match identities
```

---

## 178. Atomicity boundary

Comme pour les autres providers :

```text
local persistence commit
```

et :

```text
remote economic side effect
```

ne peuvent pas appartenir à une même ACID transaction.

D'où :

```text
Outbox
idempotency
certainty state
reconciliation
```

---

## 179. Outbox role

L'Outbox peut représenter :

```text
OrderSubmissionRequested
```

puis un dispatcher appelle IBKR.

Le résultat est ensuite persisté.

---

## 180. Command ownership

Le dispatcher doit garantir :

```text
one local command claim
```

mais ne peut pas garantir exactement-once network execution.

D'où recovery.

---

## 181. TWS local settings are part of effective provider config

Contrairement à une pure REST API, certains comportements viennent de :

```text
TWS / Gateway settings
```

Exemples :

```text
socket port
trusted IPs
precautionary settings
resubmit behavior
timezone behavior
```

---

## 182. Runtime configuration snapshot

Il pourrait être utile de capturer :

```text
effective IBKR runtime config
```

au startup pour audit.

Sans secrets.

---

## 183. Provider config drift

Si TWS settings changent entre deux runs :

```text
same code
```

peut se comporter différemment.

Il faut donc détecter au moins les settings critiques.

---

## 184. Market data source choice

IBKR lui-même indique ne pas être un market data provider spécialisé.

Pour certaines stratégies, il pourra être préférable :

```text
IBKR execution
+
external market data provider
```

---

## 185. PyTradeKit must support split providers

Cela confirme un besoin important :

```text
ExecutionProvider
!=
MarketDataProvider
```

Un runtime doit pouvoir composer :

```text
IBKR execution
Polygon market data
```

ou autre.

---

## 186. Historical data and backtest reproducibility

Comme IBKR peut ajuster/comprimer/filtrer les données historiques :

```text
re-request later
```

peut ne pas produire des bytes identiques.

Pour backtest reproductible :

```text
ingest
persist dataset
version dataset
```

reste préférable.

---

## 187. Runtime vs research separation

IBKR historical endpoints sont utiles pour :

```text
discovery
light research
runtime lookback
```

mais pas nécessairement comme data lake historique principal.

---

## 188. Market data client historical code

Le client fourni est donc pertinent comme :

```text
bootstrap connector
```

mais pas comme :

```text
canonical production market data adapter
```

sans corrections.

---

## 189. Required corrections legacy client

Minimum :

```text
fix timezone
remove symbol heuristics
use conId mapping
fix average semantic mapping
model close_time correctly
add entitlement/feed metadata
add pacing handling
separate provider errors
```

---

## 190. Pacing error handling

Ne pas faire :

```text
catch Exception
raise RuntimeError
```

pour tout.

Il faut distinguer :

```text
PacingLimitExceeded
MarketDataEntitlementMissing
ContractNotFound
ProviderDisconnected
ProviderTimeout
ProviderRejectedRequest
```

---

## 191. Error taxonomy

IBKR possède des centaines de codes.

PyTradeKit ne doit pas les copier tous.

Mapper vers catégories canoniques.

---

## 192. Error mapping candidate

```text
IBKR error
    |
    +-- Authentication / Session
    +-- Connectivity
    +-- Rate / Pacing
    +-- Contract Resolution
    +-- Market Data Entitlement
    +-- Order Validation
    +-- Order Rejection
    +-- Provider Internal
    +-- Unknown Outcome
```

---

## 193. Preserve provider code

Même après mapping canonique, conserver :

```text
provider_error_code
provider_error_message
```

pour diagnostic.

---

## 194. Error 103

IBKR :

```text
Duplicate order ID
```

Ce n'est pas :

```text
duplicate economic order
```

nécessairement.

C'est une violation de la séquence `orderId`.

---

## 195. Error 110

IBKR :

```text
price does not conform to minimum price variation
```

Cela doit déclencher :

```text
constraint refresh
```

ou local validation improvement.

---

## 196. Error 133

IBKR :

```text
Submit new order failed
```

peut avoir plusieurs causes.

Le mapping doit être conservateur.

---

## 197. Error 134

IBKR recommande de vérifier les open orders après modify failure.

Cela est une forme explicite de reconciliation.

---

## 198. Provider warnings

TWS callbacks peuvent produire :

```text
warnings
```

qui ne sont pas forcément des erreurs fatales.

Un résultat typé pourrait distinguer :

```text
accepted
accepted_with_warning
held
rejected
uncertain
```

---

## 199. Observability

Métriques candidates :

```text
ibkr_gateway_connected
ibkr_api_ready
ibkr_reconnect_total
ibkr_handshake_seconds

ibkr_order_submit_total
ibkr_order_submit_uncertain_total
ibkr_order_reject_total
ibkr_order_cancel_total

ibkr_exec_details_total
ibkr_duplicate_exec_total

ibkr_market_data_lines_used
ibkr_pacing_violation_total
ibkr_entitlement_error_total

ibkr_reconciliation_unresolved_total
```

---

## 200. Structured logs

```text
provider
transport
environment
client_id
canonical_order_id
order_ref
ib_order_id
perm_id
exec_id
con_id
account_alias
error_code
correlation_id
```

---

## 201. Sensitive fields

Éviter logs bruts de :

```text
username
password
account ID
gateway auth material
```

---

## 202. Runtime health dimensions

```text
gateway_process
socket_connection
IB backend connectivity
account session
market data entitlement
order channel
market data channel
reconciliation
```

Un seul `healthy=true` est trop pauvre.

---

## 203. Health state example

```text
READY
DEGRADED_MARKET_DATA
RECONCILING
DISCONNECTED_GATEWAY
DISCONNECTED_IB
ACCOUNT_MISMATCH
PACING_LIMITED
```

---

## 204. IB backend outages

Même si la socket locale reste ouverte :

```text
IB backend connectivity
```

peut être perdue.

Le runtime doit écouter les codes correspondants.

---

## 205. Local gateway as dependency

Nouvelle catégorie :

```text
local sidecar dependency
```

PyTradeKit doit pouvoir diagnostiquer :

```text
Gateway not running
wrong port
API disabled
untrusted IP
```

---

## 206. Process orchestration

Future deployment :

```text
IB Gateway
+
PyTradeKit worker
+
PostgreSQL
```

est une composition multi-process.

---

## 207. Gateway restart

Un restart Gateway est une vraie failure scenario à tester.

```text
kill gateway
restart
reconnect
reconcile
resume
```

---

## 208. Fault qualification

Future tests :

```text
gateway SIGTERM
TCP break
IB server outage
market data farm disconnect
order farm disconnect
reconnect
stale nextValidId
duplicate event
out-of-order callbacks
```
---

## 209. Market data farm status

IBKR expose des messages spécifiques de farm connectivity.

Ils doivent affecter :

```text
market data readiness
```

pas nécessairement :

```text
execution readiness
```

---

## 210. Separation of readiness domains

```text
ExecutionReady
MarketDataReady
PortfolioReady
```

peut être préférable à un état unique.

---

## 211. Paper execution test scope

Future IBKR Paper probe :

```text
connect gateway
verify account
qualify AAPL
read contract details
read market rules
submit tiny MARKET
observe openOrder
observe orderStatus
observe execDetails
observe commission/fees
query positions
submit LIMIT
cancel LIMIT
restart gateway
reconcile
```

---

## 212. Read-only probe first

Comme Alpaca/Binance :

```text
no orders in first probe
```

---

## 213. Read-only probe

```text
01 connect PAPER gateway
02 handshake
03 verify nextValidId
04 verify account
05 current time
06 qualify one contract
07 contract details
08 market rules
09 market data subscription
10 historical bars
11 positions
12 account summary
13 open orders
```

---

## 214. Controlled order probe

```text
01 persist canonical order
02 assign orderRef
03 allocate orderId
04 submit
05 capture openOrder
06 capture orderStatus
07 capture execDetails
08 capture permId
09 capture fees
10 LIMIT + cancel
11 reconnect scenario
12 verify recovery
```

---

## 215. Fixture set

```text
tests/fixtures/ibkr/
|
+-- contract_details_aapl.json
+-- market_rule.json
+-- open_order.json
+-- order_status_submitted.json
+-- order_status_filled.json
+-- exec_details.json
+-- commission_and_fees.json
+-- position.json
+-- account_summary.json
+-- connectivity_errors.json
```

---

## 216. Fixtures from callbacks

Comme TWS API n'est pas REST JSON nativement, les fixtures doivent représenter :

```text
normalized raw callback payload
```

pas inventer un faux HTTP format.

---

## 217. Callback sequencing tests

Tester :

```text
openOrder before orderStatus
orderStatus duplicate
execDetails before final Filled
commission after execDetails
duplicate status
reconnect replay
```

---

## 218. Duplicate callbacks

Un callback identique peut être reçu plusieurs fois.

Inbox/idempotency doit être robuste.

---

## 219. Fill idempotency

`execId` est la meilleure clé candidate.

```text
unique(provider, execId)
```

---

## 220. Order status idempotency

Pour orderStatus sans unique event ID :

```text
provider order identity
+
status
+
filled
+
remaining
+
timestamp if available
```

peut être utilisé avec précaution.

La stratégie doit être testée.

---

## 221. Event ordering

Ne pas supposer :

```text
every callback arrives once
and
in perfect semantic order
```

Le Domain doit converger.

---

## 222. Execution corrections

Les corrections `execId` rendent encore plus important :

```text
provider truth reconciliation
```

---

## 223. Commission timing

La commission peut être enrichie après le Fill.

Un workflow événementiel est préférable à un mapping bloquant.

---

## 224. Market data parsing

Toutes les observations doivent porter :

```text
provider_timestamp
received_at
source_type
entitlement_type
```

---

## 225. Timestamp parser policy

Jamais :

```text
strip timezone
replace with UTC
```

---

## 226. zoneinfo

Utiliser :

```python
zoneinfo.ZoneInfo
```

pour les conversions.

---

## 227. Exchange local timezone

Conserver au besoin :

```text
original_timezone
```

comme metadata de source.

---

## 228. useRTH

Le code historique utilise :

```text
useRTH=False
```

Cela inclut pre/post market quand disponible.

Ce choix doit être explicitement porté par la requête.

---

## 229. Backtest implication

Deux datasets avec :

```text
useRTH=True
```

et :

```text
useRTH=False
```

ne sont pas interchangeables.

---

## 230. `whatToShow`

Même logique :

```text
TRADES
MIDPOINT
```

doit faire partie de l'identité du dataset.

---

## 231. Data lineage

Pour IBKR historical data :

```text
provider
conId
exchange
whatToShow
barSize
useRTH
timezone mode
requested_at
```

devrait être enregistré.

---

## 232. Provider comparison impact

IBKR confirme plusieurs concepts issus des deux études précédentes.

---

## 233. Client order reference

```text
Alpaca
client_order_id

Binance
newClientOrderId

IBKR Web API
cOID

IBKR TWS API
orderRef
```

---

## 234. Provider order ID

```text
Alpaca
Order.id

Binance
orderId

IBKR
orderId + permId
```

IBKR révèle qu'un seul niveau d'external ID n'est pas toujours suffisant.

---

## 235. External fill ID

```text
Alpaca
execution_id

Binance
tradeId

IBKR
execId
```

Très forte convergence.

---

## 236. Unknown submission

```text
Alpaca
network uncertainty / retry risk

Binance
TIMEOUT / 5XX unknown

IBKR
socket/gateway disconnect during submit
```

Conclusion :

```text
ExecutionCertainty
```

est clairement provider-agnostic.

---

## 237. Private execution stream

```text
Alpaca
trade_updates

Binance
executionReport

IBKR
openOrder / orderStatus / execDetails
```

---

## 238. Instrument constraints

```text
Alpaca
asset/order rules

Binance
exchangeInfo filters

IBKR
ContractDetails + MarketRule
```

---

## 239. Market data entitlements

IBKR introduit une dimension plus forte :

```text
subscription entitlement
```

qui doit entrer dans capability context.

---

## 240. Environment model

```text
Alpaca
PAPER / LIVE

Binance
DEMO / TESTNET / LIVE

IBKR
PAPER / LIVE
+
TWS vs Gateway
+
TWS API vs Web API
```

Un simple enum global est insuffisant.

---

## 241. ProviderEnvironment proposal

```text
ProviderEnvironment
    provider
    mode
    transport
    endpoint/port
```

---

## 242. RuntimeSafetyMode

En parallèle :

```text
SIMULATED
SANDBOX
LIVE
```

peut exprimer l'intention globale.

---

## 243. ExecutionProvider terminology

IBKR confirme encore que :

```text
BrokerAdapter
```

est peut-être trop étroit.

Binance est exchange.

IBKR est broker + routing platform.

---

## 244. Candidate generic name

```text
ExecutionProvider
```

reste le meilleur candidat actuel.

---

## 245. MarketDataProvider separation

IBKR renforce aussi :

```text
ExecutionProvider
!=
MarketDataProvider
```

---

## 246. TWS as provider gateway

IBKR introduit :

```text
ProviderGateway
```

comme possible concept infrastructure.

---

## 247. GatewayPort abstraction

Pas un Domain port.

Possible runtime interface :

```text
ProviderSession
    connect
    disconnect
    health
    reconnect
```

---

## 248. Session-specific provider

Alpaca REST paraît relativement stateless côté client.

IBKR TWS est fortement session-oriented.

Cela justifie :

```text
ProviderSessionLifecycle
```

dans l'infrastructure.

---

## 249. Runtime composition

Future composition root :

```text
PostgreSQL
        |
        +-- repositories
        |
        +-- Outbox/Inbox

IB Gateway PAPER
        |
        +-- execution session
        |
        +-- market data session

PyTradeKit Runtime
        |
        +-- OMS
        +-- Portfolio
        +-- Risk
        +-- Strategy
```

---

## 250. Initial future scope

Recommandation IBKR future :

```text
PAPER
IB Gateway
TWS protocol
ib_async candidate
US equities
MARKET
LIMIT
CANCEL
account snapshot
position snapshot
execution callbacks
historical bars
basic quotes
```

---

## 251. Out of first scope

```text
options
futures
forex
combos
advisor accounts
allocation orders
algos
manual order adoption
Web API transport
LIVE
complex order types
market depth
```

---

## 252. Why not Web API first

Web API ajoute :

```text
OAuth
brokerage sessions
reply confirmation workflow
session exclusivity
```

alors que TWS API correspond déjà à l'expérience et au code historique.

---

## 253. Why not official ibapi first

Deux raisons :

```text
license review
callback complexity
```

Le Sync Wrapper réduit la seconde, mais pas la première.

---

## 254. Why `ib_async` is attractive

```text
BSD
async
sync
Python-native
active project
existing user experience
no ibapi dependency
```

---

## 255. Risks of `ib_async`

```text
non-official
protocol lag risk
maintainer dependency
behavior abstraction over raw callbacks
reconnection behavior must be audited
```

---

## 256. SDK gate

Avant décision :

```text
compare ib_async 2.1.0
vs
official TWS API 10.49 Sync Wrapper
```

sur :

```text
license
coverage
reconnect
order event fidelity
performance
testing
packaging
upgrade cadence
```

---

## 257. Suggested dependency strategy

Ne pas ajouter IBKR à base dependencies.

Future extra :

```toml
ibkr = [
    "ib_async==2.1.0",
]
```

uniquement après qualification.

---

## 258. Architecture fitness functions

```text
FF-IBKR-001
No ib_async imports in Domain.

FF-IBKR-002
No ibapi imports in Domain.

FF-IBKR-003
No live port in PAPER runtime.

FF-IBKR-004
No blind resubmit on reconnect.

FF-IBKR-005
All economic numbers normalized with Decimal.

FF-IBKR-006
Instrument mapping must resolve to conId.

FF-IBKR-007
Provider order IDs never replace canonical OrderId.
```

---

## 259. Legacy client fitness failures

Le client historique violerait aujourd'hui au moins :

```text
timezone correctness
instrument qualification rigor
semantic mapping of average
explicit environment hard-lock
provider error taxonomy
```

---

## 260. Legacy client positive patterns

Il possède néanmoins de bons choix :

```text
market/execution separation
readonly market connection
distinct clientId
Decimal conversions
explicit disconnect
contract qualification call
```

---

## 261. Provider risk register

### R1 - Accidental LIVE connection

Severity:

```text
CRITICAL
```

Mitigation:

```text
paper port hard lock
environment verification
account verification
```

### R2 - Blind order resubmit after reconnect

Severity:

```text
CRITICAL
```

Mitigation:

```text
audit maintainAndResubmitOrdersOnReconnect
disable implicit behavior
UNCERTAIN
reconciliation
```

### R3 - Wrong order identity

Severity:

```text
HIGH
```

Mitigation:

```text
persist orderRef
orderId
permId
clientId
```

### R4 - Wrong contract

Severity:

```text
HIGH
```

Mitigation:

```text
conId mapping
contract qualification
no symbol heuristic
```

### R5 - Timezone corruption

Severity:

```text
HIGH
```

Mitigation:

```text
ZoneInfo
UTC normalization
```

### R6 - Market data entitlement mismatch

Severity:

```text
MEDIUM/HIGH
```

Mitigation:

```text
feed state
subscription diagnostics
readiness split
```

### R7 - Pacing violation

Severity:

```text
MEDIUM
```

Mitigation:

```text
request scheduler
market data line accounting
historical pacing rules
```

### R8 - Gateway outage

Severity:

```text
HIGH
```

Mitigation:

```text
supervision
reconnect
reconciliation
```

### R9 - SDK license incompatibility

Severity:

```text
HIGH
```

Mitigation:

```text
license review
ib_async alternative
optional dependency
```

---

## 262. Paper probe gate

A future IBKR probe must demonstrate :

```text
[ ] paper port only
[ ] handshake complete
[ ] nextValidId obtained
[ ] account identity verified
[ ] one contract qualified
[ ] conId persisted
[ ] market rule loaded
[ ] orderRef roundtrip proven
[ ] permId captured
[ ] execId captured
[ ] duplicate callback handling proven
[ ] cancel-fill race observed/tested
[ ] reconnect recovery tested
[ ] no blind resubmit
[ ] no timezone corruption
[ ] market data entitlement identified
[ ] gateway restart handled
```

---

## 263. Questions ouvertes

1. `orderRef` est-il disponible et stable pour tous les retail PAPER orders que PyTradeKit vise ?
2. Quelle longueur et quelles contraintes pratiques faut-il appliquer à `orderRef` ?
3. Quand `permId` devient-il disponible après submit ?
4. Quel callback fournit le premier `permId` de manière fiable ?
5. Après une perte socket immédiatement après `placeOrder`, quel ensemble minimal de queries retrouve l'ordre ?
6. `ib_async` rejoue-t-il ou resoumet-il automatiquement des ordres lors de reconnect ?
7. Comment `ib_async` traite-t-il `maintainAndResubmitOrdersOnReconnect` ?
8. Les callbacks sont-ils rejoués après reconnect ?
9. Comment détecter sans ambiguïté un gap d'executions ?
10. Quelle source est la plus fiable pour completed orders après restart ?
11. Comment les execution corrections doivent-elles être traitées ?
12. À quel moment CommissionAndFeesReport arrive-t-il par rapport à execDetails ?
13. Quelle est la meilleure clé Inbox pour orderStatus ?
14. Quel clientId utiliser pour une première intégration PAPER ?
15. Faut-il réserver clientId 0 à recovery/manual adoption ?
16. Quelle stratégie d'orderId allocation garantit l'absence de collision ?
17. Quelle version de Gateway stable qualifier avec `ib_async 2.1.0` ?18. Quelles market data subscriptions sont disponibles sur le compte PAPER utilisé ?
19. Comment mapper delayed/frozen data dans le canonical MarketData model ?
20. Comment rendre les market data lines observables ?
21. Quelle policy appliquer après error 110 min tick violation ?
22. Comment persister les market rules et leur date d'observation ?
23. Le Web API `cOID` offre-t-il de meilleures garanties de recovery que TWS `orderRef` ?
24. Une future integration Web API doit-elle partager les mêmes mappers que TWS ?
25. Quelle stratégie de licence adopter si l'adapter officiel `ibapi` devient nécessaire ?

---

## 264. Impact immédiat sur architecture PyTradeKit

IBKR confirme que le modèle provider doit être plus riche que :

```text
BrokerClient
```

Il faut penser en :

```text
ProviderSession
ExecutionAdapter
ExecutionEventReceiver
SnapshotAdapter
InstrumentResolver
ConstraintProvider
MarketDataAdapter
```

---

## 265. Strong canonical concepts after 3 providers

Après Alpaca, Binance et IBKR :

```text
OrderId
ClientOrderReference
ProviderOrderIdentity
FillId
ExternalFillId
ExecutionCertainty
ProviderInstrumentMapping
InstrumentTradingConstraints
Inbox
Outbox
Reconciliation
ProviderEnvironment
CapabilityContext
```

apparaissent fortement justifiés.

---

## 266. Concepts still to design

```text
ProviderSession
RateLimit/Pacing snapshot
Fee enrichment
Execution correction
Gateway supervision
Provider order identity exact schema
Transport-aware capability model
```

---

## 267. Document sequencing

Les documents discovery deviennent :

```text
39_PYTRADEKIT_ALPACA_API_SDK_INTEGRATION_ANALYSIS.md

40_PYTRADEKIT_BINANCE_SPOT_API_SDK_INTEGRATION_ANALYSIS.md

41_PYTRADEKIT_IBKR_API_SDK_INTEGRATION_ANALYSIS.md

42_PYTRADEKIT_PROVIDER_COMPARATIVE_ARCHITECTURE.md
```

Le document comparatif précédemment envisagé en 41 devient donc 42.

---

## 268. Recommended discovery roadmap

```text
LOT-04A
Alpaca API & SDK analysis
DONE

LOT-04B
Binance Spot architecture validation
DONE

LOT-04C
IBKR architecture validation
DONE with this document

LOT-04D
Provider comparative architecture
NEXT

LOT-04E
Alpaca PAPER read-only probes

LOT-04F
Alpaca controlled order probes

LOT-04G
Alpaca integration contract freeze

LOT-05
PAPER Runtime Configuration
```

---

## 269. Why IBKR remains out of 0.5 implementation

Ajouter IBKR maintenant introduirait :

```text
local gateway
TCP protocol
new SDK
new licensing concerns
clientId lifecycle
order ID allocator
contract qualification
market data subscriptions
new recovery scenarios
```

Le milestone deviendrait trop large.

---

## 270. Correct strategy

```text
study three providers
design common contracts
implement one provider
qualify
then add others
```

---

## 271. Provider comparison preview

| Concept | Alpaca | Binance Spot | IBKR |
|---|---|---|---|
| Client order reference | `client_order_id` | `newClientOrderId` | `orderRef` / `cOID` |
| Provider order ID | UUID | `orderId` | `orderId`, `permId` |
| External fill ID | `execution_id` | `tradeId` | `execId` |
| Private execution facts | `trade_updates` | `executionReport` | `orderStatus`, `execDetails` |
| Instrument identity | asset/symbol | symbol | `conId` |
| Constraints | provider rules | exchange filters | ContractDetails + MarketRule |
| Sandbox | PAPER | Demo/Testnet | PAPER |
| Transport | REST/WS | REST/WS | TCP Gateway / REST+WS |
| Session state | moderate | moderate | strong |
| Market data entitlement | plan/feed | exchange public | subscriptions/lines |
| Retry risk | SDK REST | SDK REST | reconnect/resubmit behavior |
| Runtime sidecar | no | no | TWS/IB Gateway |

---

## 272. Key architectural result

IBKR démontre que :

```text
client_order_id
```

ne doit pas être modélisé comme :

```text
one provider string
```

mais comme une famille de provider identities.

---

## 273. Proposed ProviderOrderIdentity

```text
ProviderOrderIdentity
    provider
    client_reference
    session_order_id
    permanent_order_id
    account_reference
    provider_session_reference
```

Tous les champs sauf provider et canonical mapping peuvent être optionnels.

---

## 274. Avoid provider leakage

Le Domain ne doit jamais connaître :

```text
clientId
nextValidId
permId
conId
EClient
EWrapper
IB
Contract
```

---

## 275. Application may know canonical provider identity

L'application peut manipuler :

```text
ProviderOrderIdentity
```

sans connaître les noms IBKR spécifiques.

---

## 276. Infrastructure mapping

```text
IBKR orderId
-> session_order_id

IBKR permId
-> permanent_order_id

IBKR orderRef
-> client_reference
```

---

## 277. ProviderInstrumentIdentity

Concept possible :

```text
ProviderInstrumentIdentity
    provider
    external_id
    external_symbol
    venue
```

IBKR :

```text
external_id = conId
```

---

## 278. Account reconciliation importance

Avec IBKR :

```text
manual TWS trading
```

est réaliste.

PyTradeKit devra à terme supporter :

```text
external activity detected
```

même si l'ordre ne vient pas du runtime.

---

## 279. 0.6 relevance

Cela correspond parfaitement au futur milestone :

```text
Reconciliation & Recovery
```

IBKR sera probablement un excellent provider de qualification de 0.6.

---

## 280. Final recommendation

Ne pas implémenter IBKR dans 0.5.

Utiliser cette étude pour enrichir le design provider.

Puis produire :

```text
42_PYTRADEKIT_PROVIDER_COMPARATIVE_ARCHITECTURE.md
```

avant LOT-05.

---

## 281. Sources officielles

### API Home

```text
https://www.interactivebrokers.com/docs/
```

### TWS API introduction

```text
https://www.interactivebrokers.com/docs/tws-api/doc/introduction
```

### TWS API changelog

```text
https://www.interactivebrokers.com/docs/tws-api/changelog
```

### Sync Wrapper

```text
https://www.interactivebrokers.com/docs/tws-api/sync-doc/introduction
```

### Connectivity

```text
https://www.interactivebrokers.com/docs/tws-api/doc/connectivity/verify-api-connection
```

### Place Order

```text
https://www.interactivebrokers.com/docs/tws-api/doc/orders/place-order/introduction
```

### Order reference

```text
https://www.interactivebrokers.com/docs/tws-api/ref/order
```

### Execution

```text
https://www.interactivebrokers.com/docs/tws-api/ref/execution
```

### Contract details

```text
https://www.interactivebrokers.com/docs/tws-api/ref/contract-details
```

### Contracts

```text
https://www.interactivebrokers.com/docs/tws-api/contracts/introduction
```

### Market data

```text
https://www.interactivebrokers.com/docs/tws-api/doc/md/introduction
```

### TWS limitations

```text
https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/tws-api-limitations
```

### Error codes

```text
https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes
```

### Web API

```text
https://www.interactivebrokers.com/docs/web-api/introduction
```

### Web API orders

```text
https://www.interactivebrokers.com/docs/web-api/v1/endpoints/orders/place-order
```

### WebSocket

```text
https://www.interactivebrokers.com/docs/web-api/ws/introduction
```

### ib_async

```text
https://github.com/ib-api-reloaded/ib_async
```

---

## 282. Historical implementation source

Le code historique utilisateur étudié :

```text
IBKRMarketClient
ib_async
historical bars
contract resolution
readonly market connection
```

a servi de source d'expérience interne.

Il ne constitue pas une documentation normative IBKR.

---

## 283. Final principle

> Normalize economic semantics, preserve provider operational realities.

Pour IBKR cela signifie :

```text
normalize:
Order
Fill
Balance
Position
Instrument
Execution certainty

preserve:
clientId
orderId
permId
execId
conId
market-data entitlements
Gateway lifecycle
pacing rules
transport session
```

---

## 284. Final conclusion

IBKR est probablement le provider qui teste le plus sévèrement l'architecture PyTradeKit jusqu'ici.

Alpaca valide une intégration broker REST/stream relativement moderne.

Binance valide une venue crypto avec filters, rate limits et user streams.

IBKR ajoute :

```text
local gateway
stateful TCP session
multi-level order identity
contract qualification
manual/API order coexistence
market data entitlements
gateway process lifecycle
session-specific recovery
```

Si PyTradeKit peut intégrer ces trois modèles sans contaminer son Domain, alors son architecture provider-agnostic sera nettement plus crédible.

Le prochain document doit donc être :

```text
42_PYTRADEKIT_PROVIDER_COMPARATIVE_ARCHITECTURE.md
```

Il devra décider formellement ce qui appartient :

```text
au Domain
à l'Application
au Runtime
à l'ACL provider
à la Persistence
```

avant de figer le runtime PAPER 0.5.