# 58 - PyTradeKit - LOT-05.4 IBKR Order Status & Callback Normalization

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b1  
**LOT :** LOT-05.4  
**Date :** 2026-10-23  

## 1. Objectif

LOT-05.4 normalise les callbacks IBKR d'ordre sans confondre :

~~~text
provider callback
provider cumulative state
canonical execution fact
economic fill
~~~

Les callbacks cibles sont :

~~~text
openOrder
orderStatus
error
~~~

execDetails est volontairement reserve au prochain sous-lot.

## 2. Principe

IBKR recommande de surveiller ensemble :

~~~text
error
orderStatus
openOrder
execDetails
~~~

PyTradeKit ne traite donc aucun callback unique comme une preuve economique complete.

## 3. Statuts provider connus

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

Mapping fige :

~~~text
PendingSubmit -> transient
PreSubmitted  -> ACCEPTED
Submitted     -> ACCEPTED
PendingCancel -> transient
ApiCancelled  -> CANCELLED
Cancelled     -> CANCELLED
Filled        -> FILLED state snapshot only
Inactive      -> RECONCILE
~~~

## 4. PendingCancel

~~~text
cancel request pending
!=
terminal cancellation fact
~~~

PendingCancel ne produit jamais ExecutionStatus.CANCELLED.

## 5. Filled

orderStatus expose des quantites cumulees :

~~~text
filled
remaining
avgFillPrice
lastFillPrice
~~~

Ces informations suffisent pour un snapshot d'etat mais pas pour creer un Fill.

Donc :

~~~text
Filled
-> ProviderOrderStateSnapshot(canonical_status=FILLED)
-> canonical ExecutionReport blocked
-> wait for execDetails
~~~

La meme regle s'applique a un Submitted ou PendingCancel avec filled > 0.

## 6. No synthetic Fill

LOT-05.4 ne construit aucun :

~~~text
Fill
FillId
external_fill_id
~~~

Un cumul provider ne devient jamais une execution individuelle synthetique.

## 7. Inactive

Inactive est volontairement reason-dependent.

Il peut correspondre a une situation qui n'est pas equivalente a un rejet canonique.

Donc :

~~~text
Inactive
-> canonical_status = None
-> reconciliation required
~~~

Meme la presence d'un texte rejectReason dans openOrder ne suffit pas a elle seule a produire REJECTED.

## 8. Explicit rejection evidence

L'erreur IBKR 201 est documentee comme Order rejected.

LOT-05.4 l'utilise comme preuve explicite :

~~~text
error 201
-> ExecutionStatus.REJECTED
~~~

Le message provider brut et advancedOrderRejectJson ne sont pas copies dans le motif canonique.

Le motif canonique est stable et sanitise.

## 9. Explicit cancellation evidence

L'erreur IBKR 202 est documentee comme Order cancelled.

LOT-05.4 la normalise vers :

~~~text
ExecutionStatus.CANCELLED
~~~

## 10. Other error codes

Les autres codes ne sont pas devines en terminal state dans ce sous-lot.

Exemple :

~~~text
133 Submit new order failed
~~~

peut avoir des causes differentes.

LOT-05.4 retourne donc aucune transition canonique terminale pour ces codes.

La taxonomie complete des erreurs et des issues incertaines reste dans l'ACL/runtime.

## 11. Callback ordering

L'ordre reseau des callbacks n'est pas suppose deterministe.

Le normalizer supporte :

~~~text
orderStatus before openOrder
~~~

en utilisant le contexte canonique et le registre d'identite.

Si openOrder revele ensuite un orderRef conflictuel, le conflit est traite comme erreur de protocole.

## 12. Identity requirements

orderStatus contient notamment :

~~~text
orderId
permId
clientId
~~~

Le mapper preserve :

~~~text
clientId + orderId
-> routing identity

permId
-> durable provider order identity
~~~

Un snapshot provider-neutral exige un permId non nul.

Sans permId :

~~~text
reconciliation required
~~~

## 13. openOrder

openOrder enrichit le registre avec :

~~~text
clientId
orderId
orderRef
permId
OrderState.status
OrderState.rejectReason
~~~

Il ne produit pas directement un fait economique.

## 14. Unknown statuses

Un statut provider inconnu n'est jamais mappe par defaut.

~~~text
unknown provider status
-> RECONCILE
~~~

Cela rend l'ACL robuste a une evolution future du provider.

## 15. Fitness functions

~~~text
FF-101 No IBKR SDK import in callback normalizer.
FF-102 PendingCancel never means terminal CANCELLED.
FF-103 Filled callback state never creates synthetic Fill.
FF-104 Inactive never maps directly to REJECTED.
FF-105 Error 201 is the explicit rejection fact.
FF-106 Error 202 is the explicit cancellation fact.
FF-107 Unknown statuses require reconciliation.
FF-108 Callback ordering does not assume openOrder before orderStatus.
FF-109 permId remains required for provider-neutral order snapshots.
FF-110 Raw rejection payload is not copied into canonical reason text.
~~~

## 16. Sources provider

Official IBKR TWS API documentation consulted:

~~~text
https://www.interactivebrokers.com/docs/tws-api/doc/orders/place-order/introduction
https://www.interactivebrokers.com/docs/tws-api/doc/orders/place-order/order-placement-considerations
https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes
https://www.interactivebrokers.com/docs/tws-api/ref/order
https://www.interactivebrokers.com/docs/tws-api/changelog
~~~

## 17. Next

~~~text
LOT-05.5
IBKR Execution Details & Fill Mapping
~~~
