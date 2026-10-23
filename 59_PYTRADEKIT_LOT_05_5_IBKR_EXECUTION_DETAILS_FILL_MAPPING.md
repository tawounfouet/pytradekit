# 59 - PyTradeKit - LOT-05.5 IBKR Execution Details & Fill Mapping

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b1  
**LOT :** LOT-05.5  
**Date :** 2026-10-23  

## 1. Objectif

LOT-05.5 transforme une observation IBKR execDetails en un Fill canonique lorsque l'identite economique et la correlation d'ordre sont suffisamment fortes.

~~~text
Contract + Execution
-> IBKRExecutionDetailsObservation
-> identity verification
-> execId deduplication
-> Fill
-> ExecutionReport
~~~

Aucun appel reseau n'est effectue.

## 2. Provider evidence

Le mapping retient notamment :

~~~text
Contract.conId
Contract.symbol
Execution.execId
Execution.orderId
Execution.permId
Execution.clientId
Execution.orderRef
Execution.side
Execution.shares
Execution.price
Execution.cumQty
Execution.avgPrice
Execution.exchange
Execution.acctNumber
Execution.time
Execution.pendingPriceRevision
~~~

## 3. Execution identity

IBKR documente :

~~~text
each partial fill has a separate execId
~~~

Donc :

~~~text
Execution.execId
-> ProviderFillIdentity.external_fill_id
-> Fill.external_fill_id
~~~

Le FillId canonique est deterministe a partir de l'execId provider.

## 4. One economic effect

Invariant :

~~~text
one real execId
=
one canonical economic Fill effect
~~~

Un replay exact du meme execId retourne aucune nouvelle transition economique.

~~~text
same execId replay
-> DUPLICATE
-> no second Fill
~~~

## 5. Execution corrections

IBKR documente qu'une correction d'execution est signalee par un execId qui ne differe d'un execId precedent que par les caracteres apres le dernier point.

Exemple :

~~~text
EXEC.01.01
EXEC.01.02
~~~

LOT-05.5 traite cette relation comme :

~~~text
same correction family
+
different final revision
-> CORRECTION
-> reconciliation required
-> no second canonical Fill
~~~

Le core PyTradeKit ne possede pas encore de semantique generique d'amendement d'un Fill deja applique.

Le provider adapter ne fabrique donc pas une seconde execution economique.

## 6. Partial versus final

Execution.cumQty est comparee a la quantite canonique attendue.

~~~text
cumQty < expected_quantity
-> PARTIALLY_FILLED

cumQty == expected_quantity
-> FILLED

cumQty > expected_quantity
-> protocol error
~~~

Cette decision ne depend pas de l'ordre d'arrivee de orderStatus et execDetails.

## 7. Fill quantity

~~~text
Execution.shares
-> Fill.quantity
~~~

Chaque execDetails represente l'execution courante, pas la quantite cumulee.

Le mapper exige :

~~~text
cumQty >= shares
~~~

## 8. Fill price

~~~text
Execution.price
-> Fill.price
~~~

La devise provient du ProviderExecutionContext et doit correspondre a l'instrument IBKR qualifie.

Les valeurs financieres restent en Decimal.

Aucune conversion float n'est introduite dans l'ACL.

## 9. Price revision pending

IBKR expose pendingPriceRevision pour indiquer que le prix d'execution peut encore changer.

Donc :

~~~text
pendingPriceRevision = true
-> no canonical Fill
-> reconciliation required
~~~

L'execId n'est pas marque comme applique avant resolution.

## 10. Order correlation

LOT-05.5 exige la coherence simultanee de :

~~~text
clientId + orderId
permId
orderRef
canonical ProviderExecutionContext
~~~

Le permId devient l'external_order_id du rapport.

Le orderId reste uniquement une identite de routage provider.

## 11. Instrument correlation

Le Contract associe au callback doit correspondre a l'instrument deja qualifie :

~~~text
Contract.conId
=
ProviderInstrumentIdentity.external_id

Contract.symbol
=
ProviderInstrumentIdentity.external_symbol
~~~

Un mismatch est une erreur de protocole.

## 12. Side correlation

~~~text
BOT -> BUY
SLD -> SELL
~~~

Le side provider doit correspondre au side de l'ordre canonique.

Sinon :

~~~text
ProviderProtocolError
~~~

## 13. Time normalization

La documentation IBKR expose des temps d'execution tels que :

~~~text
YYYYMMDD HH:MM:SS US/Eastern
~~~

et certains filtres supportent la forme UTC :

~~~text
YYYYMMDD-HH:MM:SS
~~~

LOT-05.5 fournit parse_ibkr_execution_time().

Pour un temps local provider :

~~~text
local wall clock
+
IANA timezone
-> timezone-aware datetime
-> astimezone(UTC)
~~~

Il est interdit de faire :

~~~text
local_time.replace(tzinfo=UTC)
~~~

Les heures locales ambiguës lors d'un changement DST sont rejetees plutot que devinees.

## 14. Commission

execDetails ne fournit pas la commission dans la semantique retenue.

Le Fill est donc cree avec :

~~~text
fee = None
~~~

LOT-05.5 ne fabrique aucun frais.

Un futur traitement de commissionReport devra etre semantiquement separe si necessaire.

## 15. Provider history

Les executions peuvent egalement provenir de reqExecutions.

Le meme mapper peut etre reutilise pour cette evidence, mais la retention provider est bornee.

La reconciliation ne doit donc pas dependre uniquement de l'historique d'executions IBKR.

## 16. Fitness functions

~~~text
FF-111 No IBKR SDK import in execution mapper.
FF-112 execId is the external Fill identity.
FF-113 Exact execId replay creates no second effect.
FF-114 Execution correction creates no second Fill.
FF-115 pendingPriceRevision blocks Fill emission.
FF-116 cumQty cannot exceed canonical order quantity.
FF-117 BOT/SLD must match canonical order side.
FF-118 conId and symbol must match resolved instrument.
FF-119 Zoned provider time is converted, never relabeled as UTC.
FF-120 Financial execution values remain Decimal.
~~~

## 17. Sources provider

Official IBKR TWS API documentation consulted:

~~~text
https://www.interactivebrokers.com/docs/tws-api/ref/execution
https://www.interactivebrokers.com/docs/tws-api/doc/order-management/execution-details/the-execution-object
https://www.interactivebrokers.com/docs/tws-api/sync-doc/executions
~~~

## 18. Next

~~~text
LOT-05.6
IBKR Account, Balance & Position Mapping
~~~
