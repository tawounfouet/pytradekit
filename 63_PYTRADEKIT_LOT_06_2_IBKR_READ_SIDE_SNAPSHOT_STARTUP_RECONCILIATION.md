# 63 - PyTradeKit - LOT-06.2 IBKR Read-Side Snapshot & Startup Reconciliation

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b3  
**LOT :** LOT-06.2  
**Date :** 2026-10-23  

## 1. Objectif

LOT-06.2 relie la session IBKR synchronisee de LOT-06.1 au pipeline generique de reconciliation sans encore qualifier les ecritures economiques.

Le sous-lot couvre :

~~~text
accountValues()
portfolio()
trades()
fills()
-> SDK-free LOT-05 semantics
-> BrokerSnapshot
-> SnapshotCompleteness
-> startup reconciliation
-> CONSISTENT / HIGH evidence
~~~

Le sous-lot ne couvre pas encore :

~~~text
placeOrder
cancelOrder
economic-write retry policy at runtime
real PAPER C3 execution evidence
LATEST_QUOTE
LIVE
~~~

## 2. Source read-side

IBAsyncPaperTransport expose uniquement la facade synchronisee :

~~~text
accountValues
portfolio
trades
fills
~~~

Le client brut ib_async reste encapsule.

## 3. Reutilisation des mappings LOT-05

Account et balance :

~~~text
AccountReady
TotalCashValue
NetLiquidation
BuyingPower
...
-> IBKRAccountSummaryObservation
-> map_ibkr_account_snapshot
~~~

Positions :

~~~text
PortfolioItem
-> IBKRPortfolioPositionObservation
-> map_ibkr_position_snapshot
~~~

Orders :

~~~text
Trade.order
Trade.orderStatus
-> permId durable
-> orderRef optional correlation
-> ibkr_order_status_rule
-> CanonicalOrder
~~~

Fills :

~~~text
Fill.execution
-> execId
-> permId
-> orderRef
-> IBKRExecutionDetailsObservation validation
-> CanonicalFill
~~~

## 4. Instrument resolution

A position provider n'est jamais mappee par symbole seul.

Le runtime exige :

~~~text
conId + symbol
-> IBKRInstrumentResolver
-> pre-qualified IBKRInstrumentMappingResult
~~~

Un mapping manquant degrade le snapshot en PARTIAL.

## 5. Account restrictions

LOT-05.6 a etabli que les metriques de compte ne prouvent pas :

~~~text
trading_blocked
account_blocked
~~~

LOT-06.2 conserve cette regle.

Une preuve explicite IBKRAccountRestrictionsObservation reste obligatoire avant emission de la balance canonique.

## 6. Coverage evidence

L'historique TWS API est borne selon la surface provider.

LOT-06.2 introduit :

~~~text
IBKRReadSideCoverageEvidence
~~~

avec :

~~~text
orders_complete
fills_complete
positions_complete
account_complete
evidence_source
~~~

Un inventaire non prouve complet force :

~~~text
SnapshotCompleteness.PARTIAL
~~~

Il est interdit de transformer un cache de session en historique complet par hypothese.

## 7. External activity

Un ordre avec permId stable mais sans OrderId canonique reste visible comme activite externe.

Un fill avec permId stable mais sans ordre canonique est conserve avec :

~~~text
ExternalActivityOrigin.UNKNOWN_EXTERNAL
~~~

Aucune adoption automatique n'a lieu.

## 8. Startup reconciliation

LOT-06.2 introduit :

~~~text
IBKRStartupReconciliationGate
~~~

Le gate exige :

~~~text
READY_FOR_STARTUP
+
generic reconciliation completed
+
ConsistencyStatus.CONSISTENT
+
StateConfidence.HIGH
~~~

Mais LOT-06.2 ajoute encore :

~~~text
economic_write_admission = FAIL
~~~

Donc meme un read-side parfaitement reconcilie ne devient pas encore TRADING_READY.

## 9. Fail-closed rules

Le snapshot devient PARTIAL lorsque notamment :

~~~text
AccountReady absent ou invalide
explicit account restriction evidence absent
instrument mapping absent
permId absent
fill identity invalide
pending price revision
unknown provider order state
order history coverage incomplete
execution history coverage incomplete
position inventory coverage incomplete
account inventory coverage incomplete
~~~

Une session deconnectee echoue avant toute capture.

## 10. Qualification

Le gate deterministe LOT-06.2 prouve :

~~~text
provider = ibkr
environment = PAPER
read-side canonicalization works
coverage evidence is explicit
startup reconciliation can reach CONSISTENT/HIGH
economic write admission remains false
real PAPER provider proof = false
PAPER certification claim = false
LIVE = false
~~~

## 11. Sources provider

Sources verifiees le 2026-10-23 :

~~~text
Interactive Brokers TWS API account value keys
Interactive Brokers TWS API execution documentation
Interactive Brokers TWS API connection readiness documentation
ib_async 2.1.0 API documentation
~~~

## 12. Next

~~~text
LOT-06.3
IBKR Contract Qualification & Reference Resolution Runtime
~~~

Le prochain sous-lot doit rendre la resolution conId -> InstrumentMapping exploitable avec une vraie session provider, tout en conservant les market rules et les contraintes de LOT-05.2.
