# 66 - PyTradeKit - LOT-06.5 IBKR Economic Write Execution Adapter

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b6  
**LOT :** LOT-06.5  
**Date :** 2026-10-23  

## 1. Objectif

LOT-06.5 introduit le premier vrai chemin d'economic write IBKR dans le codebase.

Le flux cible est :

~~~text
canonical Order
-> qualified IBKR execution binding
-> LOT-05.3 placement command
-> LOT-06.4 session reservation
-> SDK Contract + Order
-> one placeOrder call
-> Trade
-> permId if available
-> SubmissionResult
~~~

Le lot implemente egalement le cancel provider :

~~~text
canonical Order
-> reserved session route
-> synchronized Trade
-> one cancelOrder call
-> CancelResult
~~~

## 2. Safety boundary

LOT-06.5 introduit un token provider-local explicite :

~~~text
IBKREconomicWriteAdmission
~~~

Il exige :

~~~text
paper_endpoint_verified = true
account_ready = true
reconciliation_complete = true
api_read_only = false
economic_write_enabled = true
~~~

Si l'une de ces conditions est absente :

~~~text
economic write admission = closed
~~~

Ce token ne remplace pas les gates generiques de securite, risque, autorisation et runtime.

## 3. SDK placement

Le SDK reste confine dans la boundary IBKR.

LOT-06.5 construit dynamiquement :

~~~text
ib_async.Contract
ib_async.Order
~~~

Le Contract recoit conId, symbol, secType, exchange, primaryExchange, currency, localSymbol et tradingClass.

L'Order recoit orderId, action, totalQuantity, orderType, tif, orderRef, transmit, outsideRth, whatIf, overridePercentageConstraints, account et lmtPrice pour LIMIT.

Le Decimal canonique est conserve pour quantity et lmtPrice.

## 4. Session orderId

LOT-06.5 n'alloue pas lui-meme un nouvel orderId pendant placeOrder.

~~~text
nextValidId synchronized sequence
-> getReqId
-> IBKRSessionOrderId
-> reservation
-> SDK Order.orderId
~~~

La implementation ib_async utilise l'orderId deja defini si celui-ci est non nul.

## 5. Provider call cardinality

Le code contient exactement un call site client.placeOrder et un call site client.cancelOrder.

Aucun mecanisme de retry automatique n'existe autour de ces appels.

## 6. Submission uncertainty

Une fois placeOrder appele, toute exception devient SubmissionStatus.UNCERTAIN.

Le runtime ne peut pas conclure qu'aucun ordre n'a ete cree. Aucun second placeOrder n'est emis.

## 7. Immediate Trade result

Le Trade retourne est valide contre clientId, orderId, orderRef, account et la coherence permId.

Si le Trade n'est pas qualifiable apres le write, le resultat est UNCERTAIN et exige reconciliation.

## 8. Durable external order identity

Le seul identifiant IBKR autorise comme canonical external_order_id est un permId non nul.

orderId, clientId et clientId + orderId ne deviennent jamais external_order_id.

Si permId est encore nul au retour de placeOrder, le resultat immediat reste UNCERTAIN.

## 9. ACK semantics

Un submit immediat est ACKNOWLEDGED uniquement lorsque placeOrder retourne, l'identite Trade correspond a la reservation, un permId non nul est observable et son binding reussit.

## 10. LIMIT orders

Les LIMIT a static tick peuvent etre executees apres validation LOT-05.3.

Les LIMIT avec IBKRPriceIncrementMode.MARKET_RULE restent bloquees avant economic write tant que reqMarketRule n'est pas qualifie.

LOT-06.5 n'invente pas une formule de tick dynamique.

## 11. Cancel semantics

Le cancel exige une reservation LOT-06.4 et un Trade synchronise dont l'identite est validee.

Un seul cancelOrder est emis. ACKNOWLEDGED signifie que la requete a ete emise, pas que l'etat terminal CANCELLED est prouve.

## 12. Cancel uncertainty

Toute exception apres tentative cancelOrder donne CancelStatus.UNCERTAIN. Aucun retry automatique n'est emis.

## 13. query_order

IBKRExecutionAdapter implemente submit, cancel et query_order.

query_order reutilise LOT-06.4 callback correlation et LOT-05.4 status normalization. Aucun Fill n'est fabrique depuis orderStatus.

## 14. Production readiness

LOT-06.5 implemente l'economic write path mais ne le certifie pas encore contre une vraie session PAPER.

Le startup gate reste ferme avec :

~~~text
IBKR economic write path is not PAPER certified yet
~~~

Implementation present = true, real PAPER certification = false, TRADING_READY = false.

## 15. Qualification deterministe

Le gate CI prouve :

~~~text
single placeOrder call site
single cancelOrder call site
no retry
explicit write admission
pre-write order reservation
permId-only external identity
static LIMIT write path
dynamic market-rule LIMIT blocked
post-write exception -> UNCERTAIN
permId=0 -> UNCERTAIN
known permId -> ACKNOWLEDGED
cancel exception -> UNCERTAIN
query callback reuse
SDK isolation
LIVE unavailable
~~~

## 16. Provider evidence

LOT-06.5 ne produit pas de C3 PAPER evidence. Le gate est deterministe et provider-free. Aucun ordre reel PAPER n'est envoye par CI.

## 17. Provider sources

Sources verifiees le 2026-10-23 : ib_async 2.1.0 IB.placeOrder, IB.cancelOrder, Order model, MarketOrder, LimitOrder et documentation TWS API.

## 18. Next

~~~text
LOT-06.6
IBKR Pacing, Reconnect & Dynamic Market Rule Runtime
~~~

Le prochain sous-lot doit qualifier reqMarketRule, dynamic LIMIT price validation, reconnect sans economic replay, pacing containment et transitions 1100 / 1101 / 1102 / 1300.
