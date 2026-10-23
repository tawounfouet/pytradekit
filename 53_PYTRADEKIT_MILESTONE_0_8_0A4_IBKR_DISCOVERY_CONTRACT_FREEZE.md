# 53 - PyTradeKit - Milestone 0.8.0a4 IBKR Discovery & Contract Freeze

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release candidate :** 0.8.0a4  
**LOT :** LOT-04  
**Date :** 2026-10-23  
**Statut :** Contract freeze before IBKR implementation  
**Provider :** Interactive Brokers  
**Environment :** PAPER only  
**Transport cible :** TWS API socket via IB Gateway  

---

## 1. Objectif

LOT-04 transforme l'analyse exploratoire IBKR en un contrat d'implementation fige.

Il ne doit pas encore produire :

~~~text
IBKRExecutionAdapter
IBKR snapshot adapter
IBKR reconciliation runtime
IBKR PAPER order execution
IBKR CertifiedCapability
~~~

Le but est de repondre a cette question :

> Le BrokerAdapterContract 1.0-rc1 peut-il representer IBKR sans introduire de logique IBKR dans Domain, OMS, Portfolio, Risk, Reconciliation ou Safety ?

La reponse de LOT-04 est :

~~~text
YES
~~~

sous les mappings et limites decrits dans ce document.

---

## 2. Surface technique cible

La premiere integration est figee sur :

~~~text
TWS API
+
IB Gateway
+
PAPER
+
US equities
+
MARKET
+
LIMIT
+
CANCEL
+
DAY
~~~

Le Web API IBKR est explicitement hors scope de la premiere integration.

TWS est supporte comme surface de diagnostic, mais le runtime automatise cible IB Gateway.

---

## 3. Ports PAPER et LIVE

Valeurs documentees par IBKR :

~~~text
TWS LIVE         7496
TWS PAPER        7497
IB Gateway LIVE  4001
IB Gateway PAPER 4002
~~~

La premiere composition runtime est figee sur :

~~~text
IB Gateway PAPER
port 4002
~~~

PyTradeKit doit refuser :

~~~text
4001
7496
~~~

dans tout runtime declare PAPER.

Il n'existe aucun fallback LIVE.

---

## 4. Readiness

Une socket ouverte ne signifie pas que le provider est pret.

Readiness minimale :

~~~text
SOCKET_CONNECTED
PROTOCOL_NEGOTIATED
NEXT_VALID_ID_RECEIVED
ACCOUNT_VERIFIED
PAPER_ENDPOINT_VERIFIED
RECONCILIATION_COMPLETE
~~~

Le callback nextValidId reste un gate important avant l'emission de commandes.

---

## 5. Identites IBKR

IBKR expose plusieurs identites avec des roles differents :

~~~text
clientId
orderId
permId
orderRef
execId
conId
~~~

Elles ne doivent jamais etre fusionnees en une seule notion provider.

Mapping LOT-04 :

~~~text
PyTradeKit client_order_id
        |
        v
IBKR orderRef

PyTradeKit external_order_id
        |
        v
IBKR permId

adapter session order routing
        |
        v
IBKR orderId

PyTradeKit external_fill_id
        |
        v
IBKR execId

PyTradeKit external instrument id
        |
        v
IBKR conId

IBKR runtime connection identity
        |
        v
clientId
~~~

---

## 6. Pourquoi permId devient external_order_id

orderId est lie au client API et a la session d'order management.

Il n'est pas l'identite stable d'un ordre au niveau du compte.

IBKR documente permId comme identifiant host de l'ordre et recommande son usage pour reconnaitre un ordre lorsque les API order IDs changent entre sessions ou utilisateurs.

Decision :

~~~text
Order.external_order_id = str(permId)
~~~

quand un permId non nul a ete observe.

Le orderId reste adapter-local.

---

## 7. Consequence sur l'acknowledgement

Le call :

~~~text
placeOrder
~~~

n'est pas une preuve economique suffisante.

Le provider produit ensuite :

~~~text
openOrder
orderStatus
execDetails
error
~~~

LOT-04 fige donc :

~~~text
placeOrder issued
+
no stable provider acknowledgement yet
=
do not invent ACKNOWLEDGED
~~~

Une soumission peut devenir ACKNOWLEDGED seulement lorsqu'une observation provider permet de rattacher un permId stable.

Sinon :

~~~text
UNCERTAIN
-> reconcile
~~~

---

## 8. Client order reference

Le candidat TWS est :

~~~text
orderRef
~~~

Il est user-customizable et associe a l'ordre pendant son cycle de vie.

Cependant la documentation le decrit historiquement comme destine aux clients institutionnels.

Decision LOT-04 :

~~~text
orderRef = candidate client reference
PAPER probe required before C3
~~~

PyTradeKit ne suppose pas encore que son comportement retail PAPER est equivalent a Alpaca client_order_id.

---

## 9. Instrument identity

IBKR recommande fortement :

~~~text
conId + exchange
~~~

pour identifier un contrat.

LOT-04 fige :

~~~text
ProviderInstrumentIdentity.external_id = str(conId)
~~~

Le symbole reste descriptif et utile pour les diagnostics, mais ne devient pas l'identite canonique.

Pour le scope initial :

~~~text
STK
SMART
USD
US equities
~~~

avec primaryExchange lorsque necessaire a la disambiguation.

---

## 10. Execution facts

IBKR expose :

~~~text
execId
~~~

pour chaque execution.

Chaque partial fill possede un execId distinct.

Une correction d'execution peut produire un identifiant apparente.

Decision :

~~~text
ProviderFillIdentity.external_fill_id = execId
~~~

LOT-05/LOT-06 devront conserver suffisamment de metadata provider pour detecter les corrections sans modifier silencieusement un Fill canonique historique.

Le modele de correction final est differe jusqu'a observation PAPER.

---

## 11. Order states

Etats IBKR importants :

~~~text
PendingSubmit
PreSubmitted
Submitted
PendingCancel
ApiCancelled
Cancelled
Filled
Inactive
~~~

Mapping candidat :

~~~text
PendingSubmit
-> SUBMITTED

PreSubmitted
-> ACCEPTED

Submitted
-> ACCEPTED

PendingCancel
-> CANCEL_REQUESTED

ApiCancelled
-> CANCELLED

Cancelled
-> CANCELLED

Filled
-> FILLED
~~~

Inactive reste reason-dependent.

Il ne doit pas etre traduit aveuglement en REJECTED.

Le mapper doit utiliser :

~~~text
orderStatus
openOrder
OrderState
error callback
advanced reject details
~~~

avant de produire une conclusion canonique.

---

## 12. Cancel semantics

La cancellation utilise le orderId de session.

Cela ne change pas l'identite canonique.

Flow cible :

~~~text
canonical Order
-> external_order_id = permId
-> adapter identity registry
-> current session orderId
-> cancelOrder
-> orderStatus / error
-> canonical cancel fact
~~~

Si le orderId courant ne peut pas etre resolu :

~~~text
do not guess
-> reconcile
~~~

---

## 13. Reconnect

Le setting IBKR :

~~~text
maintainAndResubmitOrdersOnReconnect
~~~

peut soumettre des ordres dont la transmission a ete tentee pendant une perte reseau.

Pour PyTradeKit :

~~~text
maintainAndResubmitOrdersOnReconnect = false
~~~

est un invariant de qualification.

Reconnect :

~~~text
transport restored
!=
state recovered
~~~

La reprise doit passer par reconciliation avant admission de nouveaux effets economiques.

---

## 14. Pacing

Le pacing reste provider-specific.

PyTradeKit ne doit pas introduire dans le core :

~~~text
IBKR_50_MESSAGES_PER_SECOND
IBKR_MARKET_DATA_LINES
IBKR_ERROR_100
~~~

L'adapter doit traduire les limites et erreurs en comportements canoniques.

LOT-04 retient notamment :

~~~text
error 100
-> provider rate/pacing failure

market data line exhaustion
-> capability/readiness degradation

historical data pacing
-> market-data specific limitation
~~~

---

## 15. Market data entitlements

Les subscriptions market data sont liees au username et aux permissions du compte.

Decision :

~~~text
LATEST_QUOTE certification
depends on entitlement

lack of quote entitlement
does not automatically invalidate
ACCOUNT_QUERY
ORDER_QUERY
POSITION_QUERY
BALANCE_QUERY
~~~

Les capabilities sont qualifiees independamment.

---

## 16. PAPER limitations

Le PAPER IBKR est un simulateur.

La documentation IBKR indique notamment :

~~~text
fills simulated from top of book
some order types unsupported
complex orders may behave differently
exchange-directed market partial remainder may be rejected
market orders without opposite quote may be held
~~~

Donc :

~~~text
C3 PAPER
!=
LIVE qualification
~~~

Aucune conclusion LIVE ne peut etre derivee du LOT-06 PAPER proof.

---

## 17. SDK officiel

TWS API 10.49 a ete publie le 2026-08-03.

IBKR documente :

~~~text
TWS API 10.49+ released under GPL
~~~

PyTradeKit est :

~~~text
Apache-2.0
~~~

Decision LOT-04 :

~~~text
do not bundle official ibapi 10.49+
before explicit license review
~~~

Ce document n'est pas un avis juridique.

---

## 18. ib_async

ib_async reste un candidat implementation.

Il ne fait pas partie du contrat.

Decision :

~~~text
ib_async
candidate transport
not canonical dependency
not qualified yet
~~~

Avant adoption :

~~~text
version pin
protocol compatibility
PAPER probe
disconnect tests
callback ordering tests
upgrade policy
~~~

---

## 19. Contract compatibility matrix

| Surface | Decision |
| --- | --- |
| ExecutionPort | UNCHANGED |
| BrokerSnapshotPort | UNCHANGED |
| ProviderOrderIdentity | UNCHANGED_WITH_MAPPING |
| ProviderFillIdentity | UNCHANGED_WITH_MAPPING |
| ProviderInstrumentIdentity | UNCHANGED_WITH_MAPPING |
| Order external_order_id | permId |
| client_order_id | orderRef candidate |
| session routing order id | orderId adapter-local |
| external fill id | execId |
| instrument external id | conId |
| readiness | nextValidId + account + reconciliation |
| reconnect | no implicit resubmit |
| pacing | adapter-local |
| runtime profile | new IBKR adapter composition |
| official ibapi | deferred pending license review |
| Web API | deferred |

---

## 20. RuntimeProfile decision

Le RuntimeProfile actuel est volontairement gele sur Alpaca 0.5.

LOT-04 interdit une evolution de type :

~~~python
if provider == "alpaca":
    ...
elif provider == "ibkr":
    ...
~~~

dans le runtime core.

LOT-05/LOT-06 doivent introduire une composition IBKR propre au provider.

Une abstraction runtime plus generale ne sera extraite que si deux implementations prouvent un vrai contrat commun.

---

## 21. Target capabilities

Cible de la premiere integration :

~~~text
ACCOUNT_QUERY
ORDER_QUERY
MARKET_ORDER
LIMIT_ORDER
CANCEL_ORDER
PARTIAL_FILL
POSITION_QUERY
BALANCE_QUERY
CLIENT_ORDER_REFERENCE
EXECUTION_FACTS
RECONNECT_RECOVERY
LATEST_QUOTE
~~~

Differe :

~~~text
REPLACE_ORDER
~~~

---

## 22. Questions PAPER encore ouvertes

LOT-04 ne fabrique pas de reponse lorsque la documentation ne suffit pas.

Questions a verifier par probe :

~~~text
orderRef persistence and uniqueness on target PAPER account
exact callback ordering for MARKET
exact callback ordering for LIMIT
exact callback ordering for CANCEL
partial fill behavior
first observation point of non-zero permId
execution replay after reconnect
execId correction behavior
account cash tags required for canonical Balance
market data entitlement behavior
effective pacing under qualified account
~~~

---

## 23. Non-goals

~~~text
LIVE
Web API implementation
Financial Advisor accounts
multi-account allocation
options
futures
FX
CFDs
crypto
GTC
brackets
conditional orders
algo orders
replace certification
manual TWS order adoption
~~~

---

## 24. Fitness functions

LOT-04 ajoute :

~~~text
FF-061 IBKR LIVE ports rejected by PAPER freeze
FF-062 orderId cannot become canonical external_order_id
FF-063 permId is the frozen stable order identity
FF-064 execId is the frozen execution identity
FF-065 conId is the frozen instrument identity
FF-066 reconnect implicit resubmission is forbidden
FF-067 IBKR SDK imports remain outside canonical core
FF-068 LOT-04 introduces no provider-specific branch in core
FF-069 IBKR discovery makes no certification claim
FF-070 unresolved PAPER facts remain explicit
~~~

---

## 25. Gate LOT-04

LOT-04 est ferme seulement si :

~~~text
contract freeze machine-readable
architecture tests PASS
public contract tests PASS
LIVE port hard-lock PASS
identity semantics PASS
no IBKR SDK dependency added
no IBKR core branch added
release artifact qualification PASS
~~~

---

## 26. Resultat

Le resultat attendu de 0.8.0a4 n'est pas :

~~~text
IBKR works
~~~

Le resultat attendu est :

~~~text
IBKR can be implemented against the existing broker-neutral core
without introducing IBKR semantics into that core.
~~~

---

## 27. Prochaine etape

Apres LOT-04 :

~~~text
0.8.0b1
LOT-05
IBKR Anti-Corruption Layer
~~~

Le premier code SDK/provider reel ne doit commencer qu'apres ce freeze.


---

## 28. Sources officielles verifiees

Observation effectuee le 2026-10-23.

~~~text
TWS API documentation
https://www.interactivebrokers.com/docs/tws-api/

TWS API changelog
https://www.interactivebrokers.com/docs/tws-api/changelog

Connection and default ports
https://www.interactivebrokers.com/docs/tws-api/sync-doc/connect-start-connection

Connection handshake and nextValidId readiness
https://www.interactivebrokers.com/docs/tws-api/doc/connectivity/verify-api-connection

Order object
https://www.interactivebrokers.com/docs/tws-api/ref/order

Execution object
https://www.interactivebrokers.com/docs/tws-api/ref/execution

Order placement callbacks
https://www.interactivebrokers.com/docs/tws-api/doc/orders/place-order/introduction

Order modification and binding
https://www.interactivebrokers.com/docs/tws-api/doc/orders/modifying-orders

Contract identity
https://www.interactivebrokers.com/docs/tws-api/contracts/introduction

Positions
https://www.interactivebrokers.com/docs/tws-api/sync-doc/positions

Account summary
https://www.interactivebrokers.com/docs/tws-api/sync-doc/account-summary

Executions
https://www.interactivebrokers.com/docs/tws-api/sync-doc/executions

Pacing and error codes
https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes

TWS API settings
https://www.interactivebrokers.com/docs/tws-api/protobuf/api-settings-config

TWS API limitations and PAPER behavior
https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/tws-api-limitations

TWS API 10.49 GPL change
https://www.interactivebrokers.com/docs/tws-api/changelog/2026/8/3
~~~
