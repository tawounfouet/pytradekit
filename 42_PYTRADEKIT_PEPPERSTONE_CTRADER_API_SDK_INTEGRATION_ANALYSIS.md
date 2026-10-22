# 42 - PyTradeKit - Pepperstone + cTrader API & SDK Integration Analysis

**Projet :** PyTradeKit  
**Branche fonctionnelle cible :** Forex / CFD  
**Roadmap cible :** `1.2.x - cTrader / FX-CFD Expansion`  
**Milestone actuel de discovery :** `0.5.x - Persistence + Alpaca Paper`  
**Document :** Analyse d'intégration Pepperstone + cTrader  
**Version :** 1.0  
**Date :** 2026-10-22  
**Statut :** Architecture validation provider - cTrader/Pepperstone non cible d'implémentation 0.5  
**Périmètre :** cTrader Algo/cBots Python, cTrader Open API, cTrader FIX API, SDK Python officiels Spotware, Pepperstone Forex/CFD, Demo/Live, ordres, deals, positions, market data, OAuth, Twisted, rate limits, recovery et implications provider-agnostic pour PyTradeKit

---

# 1. Objet du document

Ce document approfondit la branche Forex/CFD de PyTradeKit à travers le couple :

```text
Pepperstone
+
cTrader
```

L'objectif n'est pas d'ajouter immédiatement cTrader au milestone `0.5.x`.

L'objectif est de confronter l'architecture PyTradeKit à un quatrième écosystème de trading très différent de :

```text
Alpaca
Binance Spot
IBKR
```

et de préparer la cible déjà prévue dans la roadmap :

```text
1.2.x - cTrader / FX-CFD Expansion
```

Le cas Pepperstone + cTrader est particulièrement intéressant car il sépare explicitement :

```text
broker
```

et :

```text
trading platform / API provider
```

Pepperstone fournit notamment :

```text
trading account
brokerage relationship
margin
leverage
instrument offering
pricing
liquidity access
execution
financing / swaps
commissions
regulatory relationship
```

cTrader / Spotware fournit notamment :

```text
trading platform
order workflow
positions
market data
cBots
backtesting
optimization
cloud execution
Open API
FIX API
CLI
```

Cette séparation force PyTradeKit à raisonner en termes de :

```text
ExecutionProvider
TradingPlatform
Broker
Account
Transport
```

et non autour d'un simple concept monolithique de :

```text
BrokerClient
```

---

# 2. Question centrale

La question architecturale est :

> Comment intégrer un compte Forex/CFD Pepperstone exposé par cTrader sans faire dépendre le Domain PyTradeKit ni de Pepperstone, ni de cTrader, ni de ses Protobufs, ni de Twisted, ni du protocole FIX ?

Et, plus précisément :

> Quelles primitives sont réellement canoniques entre Alpaca, Binance, IBKR et cTrader, et quelles contraintes Forex/CFD doivent rester provider-specific ?

---

# 3. Conclusion exécutive

L'analyse conduit à une recommandation claire.

Pour une future intégration PyTradeKit :

```text
Primary integration:
cTrader Open API

Optional specialized transport:
cTrader FIX API

Not the canonical integration boundary:
cBot Python
```

Le rôle recommandé de chaque surface est :

```text
cBot Python
    -> native cTrader strategy/runtime target
    -> useful for local/cloud cTrader automation
    -> useful for experiments and deployment
    -> not ideal as canonical multi-provider PyTradeKit boundary

cTrader Open API
    -> external application integration
    -> account data
    -> orders
    -> positions
    -> deals
    -> historical and realtime market data
    -> recommended primary adapter boundary for PyTradeKit

cTrader FIX API
    -> standardized low-level trading / market data session
    -> suitable for specialized execution/data paths
    -> does not expose the complete account/history surface
    -> optional future secondary transport

cTrader CLI
    -> operational/self-hosted execution tool
    -> potentially useful for cBot deployment and qualification
    -> not the canonical broker adapter
```

Le design cible est donc :

```text
                     PyTradeKit
                         |
       +-----------------+-----------------+
       |                 |                 |
       v                 v                 v
     Strategy          Risk              OMS
       |                 |                 |
       +-----------------+-----------------+
                         |
                         v
                 ExecutionProvider
                         |
                         v
              CTraderOpenApiAdapter
                         |
                         v
                  cTrader Open API
                         |
                         v
                    Pepperstone
```

---

# 4. Pourquoi Pepperstone et cTrader doivent rester séparés

Le couple commercial peut donner l'impression d'une intégration unique :

```text
Pepperstone cTrader
```

mais les responsabilités sont différentes.

Architecture réelle :

```text
              Pepperstone
                 BROKER
                    |
                    v
             cTrader backend
              / platform
                    |
        +-----------+-----------+
        |           |           |
        v           v           v
     cTrader      Open API     FIX API
       UI
        |
        v
      Algo
      cBots
```

La même technologie cTrader est utilisée par plusieurs brokers affiliés.

Par conséquent, le futur package PyTradeKit ne devrait pas être conçu autour d'un type comme :

```text
PepperstoneCTraderClient
```

mais plutôt autour de :

```text
CTraderOpenApiExecutionAdapter
```

configuré avec une identité de compte appartenant à un broker donné.

---

# 5. Conséquence provider-agnostic

La chaîne d'identité doit pouvoir exprimer :

```text
provider platform = cTrader
broker = Pepperstone
environment = DEMO
account = <provider account identity>
symbol mapping = broker/server/environment scoped
```

et non :

```text
provider = Pepperstone only
```

ou :

```text
provider = cTrader only
```

Cette distinction sera importante pour :

```text
instrument mappings
account capabilities
commercial product differences
fees
margin
leverage
symbol IDs
execution rules
```

---

# 6. Sources normatives

Hiérarchie recommandée pour l'intégration technique :

```text
1. cTrader / Spotware official documentation
2. Spotware official protocol repositories
3. Spotware official Python SDK repositories
4. Pepperstone documentation for broker/account/product facts
5. third-party repositories only as implementation evidence
```

Les pages commerciales Pepperstone ne doivent pas être utilisées comme source normative du protocole cTrader.

---

# 7. Divergence documentaire Pepperstone / cTrader

Une divergence importante apparaît dans les sources actuelles.

Certaines pages Pepperstone cTrader Automate utilisent encore un wording historique centré sur :

```text
C#
cTrader Automate
cAlgo
```

alors que la documentation cTrader actuelle expose officiellement le développement de cBots en :

```text
C#
Python
```

Pour les capacités techniques actuelles :

```text
Spotware/cTrader documentation
```

doit être considérée comme la source normative.

Pour :

```text
availability of cTrader at Pepperstone
account types
pricing
fees
broker-specific leverage
jurisdiction
```

la documentation Pepperstone reste la source pertinente.

---

# 8. Quatre surfaces d'automatisation

Le couple cTrader fournit au moins quatre voies intéressantes.

```text
1. cTrader Algo / cBots
2. cTrader Open API
3. cTrader FIX API
4. cTrader CLI
```

Elles ne répondent pas au même besoin.

---

# 9. cTrader Algo / cBots

Un cBot est une stratégie algorithmique exécutée dans l'environnement cTrader.

Modèle :

```text
cBot
  |
  v
cTrader Algo runtime
  |
  v
cTrader account
  |
  v
Pepperstone
```

Les cBots sont aujourd'hui développables en :

```text
C#
Python
```

---

# 10. Python natif pour cBots

Le support Python permet d'écrire une stratégie Python directement dans l'écosystème cTrader.

Ce modèle est intéressant pour :

```text
strategy prototyping
backtesting
optimization
local execution
cloud execution
single-broker automation
```

Il réduit fortement la friction pour un développeur Python.

---

# 11. cBots et architecture PyTradeKit

Un cBot ne doit cependant pas devenir le coeur du Domain PyTradeKit.

Anti-pattern :

```text
PyTradeKit Domain
embedded inside
cBot lifecycle
```

Cible :

```text
PyTradeKit canonical runtime
        |
        +-- optional cBot deployment target
        |
        +-- external Open API execution adapter
```

---

# 12. Pourquoi un gros cBot monolithique est insuffisant

Une stratégie PyTradeKit peut nécessiter :

```text
multiple brokers
global portfolio
central persistence
cross-provider risk
PostgreSQL
distributed monitoring
external market data
reconciliation
audit
central OMS
```

Mettre tout cela dans un cBot crée une dépendance excessive au runtime cTrader.

---

# 13. cBot comme deployment target

Une future possibilité est :

```text
PyTradeKit Strategy Interface
        |
        v
cTrader cBot adapter
```

pour des stratégies compatibles avec une exécution locale au compte.

Cela serait un produit différent du :

```text
CTraderOpenApiExecutionAdapter
```

---

# 14. Cloud cBots

cTrader Cloud permet d'exécuter des cBots à distance.

Cela peut être très utile pour :

```text
24/7 strategy execution
no local desktop dependency
broker-native operation
simple deployment
```

Mais ce runtime impose ses propres restrictions.

---

# 15. Contraintes Cloud importantes

La documentation Cloud actuelle impose des contraintes spécifiques.

Selon les fonctionnalités utilisées, le Cloud peut avoir des restrictions sur :

```text
HTTP networking
WebSocket networking
local storage
filesystem persistence
runtime lifecycle
number of running cBots
```

Ces restrictions montrent qu'un cBot Cloud ne doit pas être considéré comme un serveur Python généraliste.

---

# 16. Cloud n'est pas un remplacement du runtime PyTradeKit

PyTradeKit a besoin de :

```text
PostgreSQL
external services
provider composition
central reconciliation
long-lived durable state
```

Le cTrader Cloud reste donc un runtime de stratégie spécialisé, pas un remplacement naturel de l'application PyTradeKit.

---

# 17. cTrader CLI

cTrader fournit également un CLI utilisable pour :

```text
run cBots
list accounts
list symbols
retrieve market data
retrieve historical data
place/manage certain orders
inspect positions and deals
backtest
optimize
```

Le CLI peut devenir intéressant pour :

```text
qualification
developer tooling
deployment automation
test harnesses
```

mais il ne doit pas devenir le protocole canonique d'intégration.

---

# 18. Open API - choix principal

cTrader Open API est la surface la plus adaptée au modèle PyTradeKit.

Elle est conçue pour :

```text
external applications
```

connectées directement au backend cTrader.

Elle permet notamment :

```text
authentication
account discovery
account information
symbols
market data
historical data
orders
positions
deals
trading operations
```

---

# 19. Architecture Open API

```text
PyTradeKit
    |
    v
CTraderOpenApiAdapter
    |
    v
Spotware Open API
    |
    v
cTrader backend
    |
    v
Pepperstone account
```

Aucun cTrader Desktop n'est requis dans cette architecture.

---

# 20. Protocoles Open API

Open API supporte :

```text
Protobuf
JSON
```

Les endpoints et ports diffèrent selon le protocole.

Pour Python, l'intégration officielle se concentre historiquement sur :

```text
Protobuf
TCP/TLS
Twisted
```

---

# 21. Endpoints Open API

Pour Protobuf :

```text
DEMO:
demo.ctraderapi.com:5035

LIVE:
live.ctraderapi.com:5035
```

Pour JSON, le port officiel documenté est :

```text
5036
```

Les environnements sont séparés.

---

# 22. Demo hard-lock

Comme Alpaca PAPER, Binance Demo et IBKR PAPER, la première qualification cTrader doit être :

```text
DEMO only
```

Règle :

```text
if environment != DEMO:
    startup fails
```

pendant la phase de qualification.

---

# 23. Aucune déduction LIVE par défaut

Ne jamais faire :

```text
missing config
=> LIVE endpoint
```

Le RuntimeProfile doit imposer explicitement :

```text
CTraderEnvironment.DEMO
```

avant d'autoriser le transport.

---

# 24. Application registration

Open API nécessite une application enregistrée.

Le flow implique notamment :

```text
application client ID
application client secret
redirect URI
OAuth authorization
access token
```

L'application doit être enregistrée et approuvée selon le process cTrader.

---

# 25. OAuth 2.0

Open API utilise OAuth.

Flow conceptuel :

```text
User
  |
  v
cTrader authorization page
  |
  v
authorization code
  |
  v
token exchange
  |
  v
access token + refresh token
```

---

# 26. Authorization code

Le code d'autorisation est court-lived.

Le runtime doit donc considérer :

```text
authorization bootstrap
```

et :

```text
runtime token refresh
```

comme deux responsabilités distinctes.

---

# 27. Access scopes

cTrader expose notamment deux niveaux de scope :

```text
accounts
trading
```

`accounts` est orienté lecture.

`trading` donne accès aux opérations de trading.

---

# 28. Least privilege

Un probe read-only doit utiliser autant que possible :

```text
accounts
```

Un probe de trading nécessite :

```text
trading
```

Ne pas demander `trading` avant d'en avoir besoin.

---

# 29. Token lifecycle

Le runtime doit gérer :

```text
access token expiration
refresh token
rotation
revocation
reauthorization
```

La logique de refresh appartient à l'infrastructure.

---

# 30. SecretsPort

La configuration ne doit jamais contenir directement :

```text
client secret
access token
refresh token
FIX password
```

Elle doit contenir des références :

```text
secret://ctrader/demo/client_secret
secret://ctrader/demo/access_token
secret://ctrader/demo/refresh_token
```

---

# 31. Authentification protocol-level

Après connexion au serveur Open API, l'application effectue une authentification applicative.

Conceptuellement :

```text
connect
   |
   v
ProtoOAApplicationAuthReq
   |
   v
application authorized
```

---

# 32. Account discovery

Ensuite :

```text
ProtoOAGetAccountListByAccessTokenReq
```

permet d'obtenir les comptes associés au token.

---

# 33. Account authorization

Chaque compte ciblé est ensuite autorisé via :

```text
ProtoOAAccountAuthReq
```

avec :

```text
ctidTraderAccountId
accessToken
```

---

# 34. Readiness Open API

Une socket connectée ne suffit donc pas.

Future readiness :

```text
TLS connected
AND
application authenticated
AND
account list obtained
AND
expected account found
AND
account authenticated
AND
environment verified
AND
runtime snapshot loaded
AND
reconciliation completed
```

---

# 35. ctidTraderAccountId

Le compte cTrader possède un identifiant spécifique :

```text
ctidTraderAccountId
```

Il doit être traité comme :

```text
provider account identity
```

et non comme un identifiant canonique PyTradeKit.

---

# 36. Account identity verification

Le startup doit vérifier :

```text
expected provider account identity
```

avant READY.

Sinon :

```text
fail closed
```

---

# 37. Broker identity

Le modèle `ProtoOATrader` expose également des informations telles que :

```text
brokerName
accountType
accessRights
```

Cela permet de vérifier que le compte résolu appartient bien au broker attendu.

---

# 38. Open API account model

Le modèle account/trader contient des informations structurantes :

```text
balance
deposit asset
leverage
account type
access rights
swap free
margin settings
broker identity
```

Ces informations ne doivent pas toutes être projetées dans un simple `Balance`.

---

# 39. Account access rights

cTrader expose des droits tels que :

```text
FULL_ACCESS
CLOSE_ONLY
NO_TRADING
NO_LOGIN
```

Cela implique que :

```text
authenticated
```

ne signifie pas :

```text
can open trades
```

---

# 40. Readiness trading

Pour un runtime d'exécution :

```text
FULL_ACCESS
```

ou une capability équivalente doit être vérifiée.

---

# 41. Position accounting modes

cTrader distingue plusieurs account types :

```text
HEDGED
NETTED
SPREAD_BETTING
```

Pour PyTradeKit, les deux premiers sont particulièrement importants.

---
