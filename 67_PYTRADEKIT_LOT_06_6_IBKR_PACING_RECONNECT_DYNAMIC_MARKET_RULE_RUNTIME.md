# 67 - PyTradeKit - LOT-06.6 IBKR Pacing, Reconnect & Dynamic Market Rule Runtime

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b7  
**LOT :** LOT-06.6  
**Date :** 2026-10-23

## 1. Objectif

LOT-06.6 qualifie les protections operationnelles requises avant une vraie certification PAPER.

Le lot couvre trois axes :

~~~text
dynamic market rules
+
pacing containment
+
connectivity recovery without economic replay
~~~

## 2. Dynamic market-rule flow

~~~text
ContractDetails
-> validExchanges + marketRuleIds
-> routing exchange selection
-> reqMarketRule
-> PriceIncrement(lowEdge, increment)
-> Decimal normalization
-> active increment
-> LIMIT price validation
-> placeOrder only if valid
~~~

Le rule ID est selectionne par alignement positionnel avec l'exchange de routage qualifie.

Une grille incomplete, vide, mal ordonnee ou sans rule ID pour SMART echoue en mode fail-closed.

## 3. Price grid interpretation

PyTradeKit traite chaque lowEdge comme le debut inclusif de la tranche associee.

Pour une tranche active :

~~~text
(price - lowEdge) % increment == 0
~~~

doit etre vrai avant execution.

Cette interpretation reste provider-locale et conserve les Decimal exacts.

## 4. Cache

IBKRMarketRuleResolver conserve les rules deja resolues par marketRuleId.

Un cache hit ne pretend pas avoir effectue un nouvel appel provider.

## 5. Pacing

LOT-06.6 reutilise le throttling automatique natif de ib_async.

Configuration qualifiee :

~~~text
MaxRequests = 45
RequestsInterval = 1 second
effective ceiling = 45 requests/second
~~~

Le runtime n'ajoute pas de seconde queue concurrente.

Un parametrage depassant ce plafond est refuse.

## 6. Throttle events

Le runtime observe :

~~~text
throttleStart
throttleEnd
~~~

Pendant throttleStart :

~~~text
economic write admission = closed
~~~

throttleEnd retire le blocage transport temporaire.

Un code provider 100 reste en revanche latch jusqu'a recovery explicite.

## 7. Connectivity events

Le bridge observe :

~~~text
connectedEvent
disconnectedEvent
errorEvent
~~~

Le runtime ne confond pas socket connectivity, provider connectivity, reconciliation et market-data readiness.

## 8. Provider codes

Transitions qualifiees :

~~~text
100  -> pacing violation latch
1100 -> provider connectivity lost + reconciliation required
1101 -> restored, provider subscriptions lost + reconciliation required
1102 -> restored, data maintained + reconciliation still required if previously invalidated
1300 -> socket port reset + explicit reconnect required
2103 -> market data degraded only
2104 -> market data healthy when no resubscription remains
2110 -> provider connectivity degraded + reconciliation required
~~~

## 9. Code 1101

1101 ne bloque pas necessairement les writes apres reconciliation uniquement parce que les market-data subscriptions restent perdues.

Les admissions sont separees :

~~~text
economic write admission
market data admission
~~~

Les market-data consumers restent bloques jusqu'a mark_market_data_resubscribed().

## 10. Code 1102

1102 restaure la connectivite provider avec donnees maintenues.

Il ne restaure jamais automatiquement une reconciliation invalidee par une perte precedente.

~~~text
1100
-> 1102
-> reconciliation required
-> CONSISTENT/HIGH
-> write readmission
~~~

## 11. Explicit socket reconnect

Pour 504, 507 ou 1300 :

~~~text
unbind events
-> stop old connection
-> start PAPER connection
-> verify startup
-> bind events
-> reconciliation reconnect workflow
-> CONSISTENT/HIGH
-> write readmission
~~~

## 12. No Watchdog

LOT-06.6 n'utilise pas ib_async Watchdog.

Raison : la reprise automatique opaque peut masquer la distinction entre transport recovery et economic state recovery.

PyTradeKit conserve donc un recovery explicitement orchestre et auditable.

## 13. No economic replay

operations_runtime.py ne contient aucun placeOrder ni cancelOrder.

Le reconnect runtime ne rejoue aucune intention economique.

~~~text
transport recovery
!= economic replay
~~~

## 14. Execution integration

IBKRExecutionAdapter exige maintenant :

~~~text
IBKROperationalGuard
~~~

avant l'admission LOT-06.5.

Submit et cancel sont donc bloques avant tout appel provider si :

~~~text
disconnected
reconnect required
reconciliation incomplete
transport throttle active
pacing violation latched
unknown provider state fail-closed
~~~

## 15. Unknown provider state

Une observation provider non classifiee latch le runtime en fail-closed.

Ce latch n'est pas automatiquement efface par un simple reconnect.

## 16. Qualification deterministe

Le gate CI prouve :

~~~text
one reqMarketRule call site
one placeOrder call site preserved
one cancelOrder call site preserved
dynamic LIMIT validation before placeOrder
ib_async throttling enabled
qualified rate <= 45 requests/second
code 100 pacing latch
1100 / 1101 / 1102 / 1300 containment
2103 market-data-only degradation
reconnect -> reconciliation -> readmission
no Watchdog
no time.sleep polling
no economic replay
~~~

## 17. Certification status

LOT-06.6 reste provider-free dans CI.

~~~text
real PAPER execution evidence = false
C3 PAPER certification = false
TRADING_READY = false
LIVE = false
~~~

## 18. Next

Le prochain lot recommande :

~~~text
LOT-06.7
IBKR Real PAPER Evidence & Compliance Certification
~~~

Il devra produire les preuves provider reelles pour MARKET, LIMIT, CANCEL, callbacks, fills, reconnect et recovery.
