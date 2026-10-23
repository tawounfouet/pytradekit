# 57 - PyTradeKit - LOT-05.3 IBKR Order Command Mapping

**Projet :** PyTradeKit
**Milestone :** 0.8.x - Broker Compliance + IBKR
**Release :** 0.8.0b1
**LOT :** LOT-05.3
**Date :** 2026-10-23

## 1. Objectif

LOT-05.3 traduit un Order canonique deja valide et soumis en une commande IBKR SDK-free.

~~~text
Order
-> IBKRPlacementCommand
-> future transport
-> future placeOrder
~~~

Aucun appel reseau n'est effectue.

## 2. Mapping

~~~text
OrderSide.BUY
-> BUY

OrderSide.SELL
-> SELL

OrderType.MARKET
-> MKT

OrderType.LIMIT
-> LMT

TimeInForce.DAY
-> DAY

client_order_id
-> orderRef

Quantity.value
-> totalQuantity

limit_price.value
-> lmtPrice
~~~

## 3. Scope

LOT-05.3 accepte uniquement :

~~~text
MARKET
LIMIT
DAY
BUY
SELL
~~~

GTC reste hors scope du vertical slice courant.

## 4. Session orderId

Le mapper ne cree aucun orderId IBKR.

~~~text
canonical mapping
!=
provider sequence allocation
~~~

nextValidId et orderId appartiennent au futur transport/runtime.

## 5. Submission lifecycle

ExecutionPort.submit() recoit deja un ordre en etat SUBMITTED.

LOT-05.3 exige donc :

~~~text
Order.status == SUBMITTED
external_order_id is None
~~~

Un ordre deja lie a une identite externe ne peut pas etre transforme en nouvelle commande de placement.

## 6. Transmission

Le contrat rend l'intention explicite :

~~~text
transmit_policy = TRANSMIT
outside_regular_trading_hours = false
what_if = false
override_percentage_constraints = false
~~~

Cela evite de dependre silencieusement des defaults du SDK ou de TWS.

## 7. Price and quantity safety

Les contraintes statiques deja connues via ContractSpecification sont verifiees avant le transport.

Pour les instruments avec marketRuleIds :

~~~text
dynamic price rule
-> no fake static validation
-> provider rule remains authoritative
~~~

## 8. Precision

Les quantites et prix restent en Decimal.

LOT-05.3 ne convertit pas en float.

La conversion eventuelle vers le SDK appartient au transport et devra etre qualifiee separement.

## 9. Fitness functions

~~~text
FF-091 No IBKR SDK import in order command mapper.
FF-092 No nextValidId or session orderId allocation in mapper.
FF-093 Only SUBMITTED canonical orders can be mapped.
FF-094 Existing external_order_id blocks new placement.
FF-095 MARKET has no limit price.
FF-096 LIMIT requires a limit price.
FF-097 DAY-only scope is enforced.
FF-098 orderRef comes from client_order_id.
FF-099 Known static quantity and tick constraints are checked.
FF-100 Dynamic market-rule pricing is not reduced to fake static tick logic.
~~~

## 10. Next

~~~text
LOT-05.4
IBKR Order Status & Callback Normalization
~~~
