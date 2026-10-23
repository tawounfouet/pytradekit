# 65 - PyTradeKit - LOT-06.4 IBKR Request/Callback Correlation & Order Session Sequencing Runtime

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b5  
**LOT :** LOT-06.4  
**Date :** 2026-10-23  

## 1. Objectif

LOT-06.4 construit la couche de sequencing et de correlation necessaire avant tout premier economic write IBKR.

Le flux cible est :

~~~text
IB Gateway PAPER
-> protocol ready
-> nextValidId synchronized by ib_async
-> client.getReqId()
-> IBKRSessionOrderId
-> orderRef
-> canonical ProviderExecutionContext
-> pre-write reservation
-> openOrder / orderStatus / error correlation
-> permId binding
~~~

LOT-06.4 ne transmet aucun ordre.

Il ne couvre pas encore :

~~~text
placeOrder
cancelOrder
economic write admission
retry of economic writes
real PAPER execution evidence
C3 certification
TRADING_READY
LIVE
~~~

## 2. Sequencing source

ib_async 2.1.0 synchronise sa sequence interne pendant connect().

La connexion n'est prete qu'apres reception de nextValidId et des comptes geres.

LOT-06.4 utilise ensuite :

~~~text
client.getReqId()
~~~

Le runtime ne maintient pas une sequence concurrente independante.

## 3. Provider identity roles

Les identites restent strictement distinctes :

~~~text
clientId
-> API client identity

orderId
-> client/session routing identity

orderRef
-> PyTradeKit client correlation

permId
-> durable IBKR host order identity

OrderId
-> canonical PyTradeKit order identity
~~~

orderId n'est jamais utilise comme external_order_id canonique.

## 4. Pre-write reservation

Avant tout futur placeOrder, le runtime reserve :

~~~text
ProviderExecutionContext
+
clientId
+
session orderId
+
orderRef
~~~

dans :

~~~text
IBKROrderIdentityRegistry
IBKROrderCorrelationRegistry
~~~

Le runtime exige une sequence strictement croissante pendant sa propre session.

Une collision de route, orderRef ou OrderId canonique echoue en mode fail-closed.

## 5. Unknown callbacks

LOT-06.4 n'adopte jamais automatiquement un callback provider inconnu.

~~~text
known clientId + orderId reservation
-> eligible for internal correlation

unknown orderId
-> ignored by internal correlation

other clientId
-> ignored by internal correlation
~~~

Les activites externes restent traitees par les mecanismes read-side et reconciliation existants.

## 6. openOrder correlation

Un openOrder connu doit confirmer :

~~~text
clientId
orderId
orderRef
~~~

Le permId peut etre absent au debut.

Lorsqu'un permId non nul apparait :

~~~text
(clientId, orderId, orderRef)
-> permId
~~~

est lie dans IBKROrderIdentityRegistry.

Un orderRef contradictoire produit un ProviderProtocolError.

## 7. orderStatus correlation

orderStatus doit rester coherent entre :

~~~text
Trade.order.clientId
Trade.orderStatus.clientId

Trade.order.orderId
Trade.orderStatus.orderId

Trade.order.permId
Trade.orderStatus.permId
~~~

Une contradiction produit un ProviderProtocolError.

Les prix provider egaux a zero sont interpretes comme information absente :

~~~text
avgFillPrice = 0
-> None

lastFillPrice = 0
-> None
~~~

La quantite filled et remaining reste une observation cumulative.

Aucun Fill economique n'est cree depuis orderStatus.

## 8. Error correlation

ib_async expose errorEvent avec un reqId/orderId.

LOT-06.4 ne traite comme erreur d'ordre que les identifiants deja reserves :

~~~text
known reserved orderId
-> IBKROrderErrorObservation

unknown request ID
-> not an internal order error

negative/general request ID
-> not an internal order error
~~~

Cela evite de classer une erreur de connexion ou une requete de reference data comme rejet d'ordre.

## 9. Callback event source

La surface ib_async expose notamment :

~~~text
openOrderEvent
orderStatusEvent
errorEvent
execDetailsEvent
~~~

LOT-06.4 qualifie la normalisation et la correlation des trois premieres surfaces necessaires avant execution.

execDetails reste traite par les semantics LOT-05.5 et sera relie au chemin d'execution dans un sous-lot ulterieur.

## 10. Runtime composition

LOT-06.4 introduit :

~~~text
IBKROrderSessionRuntime
IBKROrderSessionSequencer
IBKRCallbackCorrelationRouter
IBKROrderCorrelationRegistry
IBKROrderSessionReservation
~~~

Le builder :

~~~text
build_ibkr_order_session_runtime
~~~

reutilise une IBKRPaperConnectionRuntime deja demarree.

## 11. Safe PAPER probe

Le script :

~~~text
scripts/probe_ibkr_paper_order_sequence.py
~~~

effectue :

~~~text
PAPER connect
-> protocol ready
-> synchronized getReqId reservation
-> sanitized evidence
-> disconnect
~~~

Il n'appelle jamais :

~~~text
placeOrder
cancelOrder
~~~

Le probe consomme uniquement un identifiant de la sequence locale du client.

## 12. Qualification

Le gate deterministe prouve :

~~~text
nextValidId-derived sequencing
strict monotonic reservation
canonical OrderId correlation
orderRef uniqueness
clientId + orderId routing
openOrder correlation
orderStatus correlation
permId late binding
error event discrimination
unknown callback non-adoption
no placeOrder
no cancelOrder
no economic write
real PAPER execution proof = false
PAPER certification claim = false
TRADING_READY claim = false
LIVE = false
~~~

## 13. Provider sources

Sources verifiees le 2026-10-23 :

~~~text
ib_async 2.1.0 Client API
ib_async 2.1.0 IB.placeOrder implementation
ib_async 2.1.0 openOrder wrapper implementation
ib_async 2.1.0 events documentation
IBKR OrderStatus reference
IBKR Execution reference
~~~

## 14. Next

~~~text
LOT-06.5
IBKR Economic Write Execution Adapter
~~~

Le prochain sous-lot pourra construire le premier placeOrder PAPER controle en reutilisant :

~~~text
qualified contract
+
LOT-05.3 placement command
+
LOT-06.4 session reservation
+
callback correlation
+
uncertain-outcome policy
~~~

Aucune repetition implicite d'un economic write ne devra etre autorisee.
