# 56 - PyTradeKit - LOT-05.2 IBKR Contract & Instrument Mapping

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b1  
**LOT :** LOT-05.2  
**Date :** 2026-10-23  
**Statut :** implementation candidate  
**Provider :** Interactive Brokers  

---

# 1. Objectif

LOT-05.2 transforme les informations de contrat IBKR en modeles de reference PyTradeKit sans exposer les types SDK.

Entrees provider :

~~~text
conId
symbol
secType
exchange
primaryExchange
currency
localSymbol
tradingClass
ContractDetails
~~~

Sorties canoniques :

~~~text
ProviderInstrumentIdentity
Instrument
InstrumentMapping
ContractSpecification
~~~

Les informations IBKR qui ne peuvent pas etre reduites sans perte restent dans une enveloppe ACL provider-specific.

# 2. Scope

Le scope reste celui fige par LOT-04 :

~~~text
STK
SMART
USD
US equities
~~~

Le mapper rejette pour l'instant :

~~~text
direct exchange routing
non-USD stock contract
options
futures
FX
CFDs
crypto
~~~

L'extension de ces scopes doit etre explicite.

# 3. Identite contractuelle

La documentation IBKR recommande fortement conId + exchange comme definition stable du contrat.

LOT-05.2 conserve donc :

~~~text
conId
-> ProviderInstrumentIdentity.external_id

symbol
-> ProviderInstrumentIdentity.external_symbol

exchange
-> routing_exchange

primaryExchange
-> primary_exchange
~~~

Le routing exchange et le primary exchange ne sont pas fusionnes.

# 4. Instrument canonical

Pour le vertical slice courant :

~~~text
IBKR secType STK
-> AssetClass.EQUITY

IBKR currency USD
-> Currency("USD")

IBKR symbol
-> Instrument.symbol
~~~

Le InstrumentId reste fourni par PyTradeKit.

Le conId ne devient jamais un InstrumentId.

# 5. InstrumentMapping

~~~text
InstrumentMapping.provider = "ibkr"
InstrumentMapping.external_id = str(conId)
InstrumentMapping.external_symbol = symbol
~~~

Cela reproduit le meme contrat provider-neutral utilise par Alpaca avec une semantique externe differente.

# 6. ContractSpecification

IBKR ContractDetails expose notamment :

~~~text
minTick
minSize
sizeIncrement
suggestedSizeIncrement
marketRuleIds
validExchanges
~~~

Mapping retenu :

~~~text
sizeIncrement
-> ContractSpecification.quantity_step

minSize
-> ContractSpecification.min_quantity
~~~

max_quantity et min_notional restent inconnus.

Aucune valeur n'est fabriquee.

# 7. minTick et marketRuleIds

La documentation IBKR indique que minTick est le plus petit increment de prix mais que l'increment complet peut varier selon le prix.

Les marketRuleIds permettent d'obtenir les regles de prix par palier.

Donc :

~~~text
marketRuleIds present
->
reported_min_tick retained
->
ContractSpecification.tick_size = None
~~~

Le systeme refuse ainsi de transformer un minimum provider en regle statique universelle.

Si aucun marketRuleId n'est declare :

~~~text
minTick present
->
STATIC
->
ContractSpecification.tick_size = minTick
~~~

Si aucune information n'est disponible :

~~~text
UNKNOWN
->
tick_size = None
~~~

# 8. Positional alignment

IBKR documente les marketRuleIds dans le meme ordre que validExchanges.

LOT-05.2 conserve donc l'alignement :

~~~text
validExchanges[i]
<->
marketRuleIds[i]
~~~

Une position peut contenir None si aucune rule ID n'est disponible pour cet exchange.

La longueur des deux listes doit rester identique lorsqu'elles sont toutes deux presentes.

# 9. Informations retenues dans l'ACL

L'objet IBKRInstrumentMappingResult conserve :

~~~text
routing_exchange
primary_exchange
local_symbol
trading_class
valid_exchanges
market_rule_ids
reported_min_tick
suggested_size_increment
order_types
time_zone_id
stock_type
~~~

Ces champs ne sont pas injectes dans les modeles canoniques lorsqu'aucune semantique equivalente n'existe.

# 10. Pourquoi pas ProviderInstrumentSnapshot

ProviderInstrumentSnapshot attend aussi :

~~~text
provider_status
tradable
marginable
shortable
easy_to_borrow
fractionable
~~~

ContractDetails ne fournit pas directement toutes ces observations avec la meme semantique.

LOT-05.2 refuse donc de fabriquer ces booleens.

Le mapper produit les objets de reference disponibles et conserve le reste dans son resultat provider-specific.

# 11. Separation SDK

LOT-05.2 introduit :

~~~text
IBKRContractRecord
IBKRContractDetailsRecord
~~~

Ce sont des representations SDK-free.

Le futur transport pourra convertir :

~~~text
ib_async.Contract
or
ibapi.Contract
~~~

vers ces records.

Le reste du systeme ne verra jamais le type SDK.

# 12. Fitness functions

~~~text
FF-081 Contract mapper imports no IBKR SDK.
FF-082 conId never becomes InstrumentId.
FF-083 STK mapping remains inside the frozen equity scope.
FF-084 routing exchange and primary exchange remain distinct.
FF-085 dynamic market rules are not collapsed into static tick size.
FF-086 sizeIncrement maps only to quantity_step.
FF-087 minSize maps only to min_quantity.
FF-088 unknown constraints remain None.
FF-089 SDK-free IBKR records do not leak into canonical layers.
FF-090 ContractSpecification remains IBKR-free.
~~~

# 13. Gate LOT-05.2

~~~text
conId mapping PASS
STK scope PASS
SMART routing PASS
USD scope PASS
primaryExchange retention PASS
market rule preservation PASS
static tick behavior PASS
quantity constraints PASS
public contract PASS
architecture isolation PASS
mypy PASS
Ruff PASS
full suite PASS
release artifacts PASS
~~~

# 14. Resultat attendu

LOT-05.2 doit prouver :

~~~text
IBKR contract semantics
can be normalized into existing reference models
without pretending that provider-only constraints are universal.
~~~

La conclusion attendue reste :

~~~text
broker-neutral core change required = false
~~~

# 15. Prochaine etape

~~~text
LOT-05.3
IBKR Order Command Mapping
~~~

Il devra traduire les commandes PyTradeKit MARKET / LIMIT / DAY vers une representation IBKR SDK-free avant branchement du transport.
