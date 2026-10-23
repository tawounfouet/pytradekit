# 64 - PyTradeKit - LOT-06.3 IBKR Contract Qualification & Reference Resolution Runtime

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b4  
**LOT :** LOT-06.3  
**Date :** 2026-10-23  

## 1. Objectif

LOT-06.3 remplace la resolution instrument statique de LOT-06.2 par une resolution reference provider exploitable sur une session IBKR PAPER.

Le flux cible est :

~~~text
canonical InstrumentId
+
IBKR conId
+
symbol
-> reqContractDetails
-> ContractDetails
-> SDK-free normalization
-> LOT-05.2 mapping
-> IBKRInstrumentMappingResult
-> read-side reconciliation
~~~

Le sous-lot reste strictement read-only.

Il ne couvre pas encore :

~~~text
placeOrder
cancelOrder
reqMarketRule execution
dynamic tick validation at order time
real PAPER C3 order evidence
LATEST_QUOTE
LIVE
~~~

## 2. Provider API

La surface provider utilise :

~~~text
IB.reqContractDetails(contract)
~~~

La requete est construite par :

~~~text
Contract(
    conId=<qualified provider id>,
    exchange="SMART",
)
~~~

Le conId reste l'identite provider de reference.

Le symbole reste une preuve supplementaire de coherence.

## 3. Exact match semantics

La resolution suit les regles suivantes :

~~~text
0 provider result
-> unresolved
-> None

1 exact conId + symbol result
-> normalize
-> LOT-05.2 mapping
-> resolved

more than 1 exact match
-> protocol failure

provider result but no exact conId + symbol match
-> protocol failure
~~~

Le runtime ne choisit jamais arbitrairement un contrat parmi plusieurs resultats.

## 4. Canonical InstrumentId

LOT-06.3 n'invente jamais un InstrumentId.

Le runtime exige :

~~~text
IBKRCanonicalInstrumentIdResolver
~~~

Le resolver doit fournir le mapping :

~~~text
(conId, symbol)
-> InstrumentId
~~~

Si aucune identite canonique n'existe :

~~~text
provider lookup is skipped
resolution = None
~~~

Cela evite qu'une simple observation provider cree silencieusement un nouvel instrument canonique.

## 5. ContractDetails normalization

Les champs provider retenus sont :

~~~text
Contract.conId
Contract.symbol
Contract.secType
Contract.exchange
Contract.primaryExchange
Contract.currency
Contract.localSymbol
Contract.tradingClass

ContractDetails.minTick
ContractDetails.minSize
ContractDetails.sizeIncrement
ContractDetails.suggestedSizeIncrement
ContractDetails.validExchanges
ContractDetails.marketRuleIds
ContractDetails.orderTypes
ContractDetails.timeZoneId
ContractDetails.stockType
~~~

Ils sont convertis en :

~~~text
IBKRContractRecord
IBKRContractDetailsRecord
~~~

avant appel de :

~~~text
map_ibkr_stock_contract
~~~

## 6. Numeric provider defaults

Les valeurs provider egales a zero pour :

~~~text
minTick
minSize
sizeIncrement
suggestedSizeIncrement
~~~

sont interpretees comme information non qualifiee :

~~~text
0
-> None
~~~

LOT-06.3 n'interprete donc pas un zero provider par defaut comme une contrainte economique prouvee.

Les valeurs negatives, non numeriques ou non finies sont rejetees.

## 7. marketRuleIds

IBKR expose :

~~~text
validExchanges = "SMART,NASDAQ,..."
marketRuleIds = "26,26,..."
~~~

Les listes sont positionnellement alignees.

LOT-06.3 preserve les slots manquants :

~~~text
validExchanges = "SMART,NASDAQ,NYSE"
marketRuleIds = "26,,28"

->

("SMART", "NASDAQ", "NYSE")
(26, None, 28)
~~~

Aucune perte d'alignement n'est autorisee.

## 8. Price increment semantics

Les regles LOT-05.2 restent inchangees :

~~~text
marketRuleIds present
-> IBKRPriceIncrementMode.MARKET_RULE
-> canonical tick_size = None

no marketRuleIds
+
positive minTick
-> IBKRPriceIncrementMode.STATIC
-> canonical tick_size = minTick

neither
-> IBKRPriceIncrementMode.UNKNOWN
-> canonical tick_size = None
~~~

La presence de minTick ne suffit donc jamais a fabriquer un tick statique lorsque des market rules existent.

## 9. Cache

IBKRContractReferenceResolver maintient un cache local :

~~~text
(conId, symbol)
-> IBKRInstrumentMappingResult
~~~

Un mapping exact deja qualifie evite une seconde requete provider.

Le cache ne peut pas etre silencieusement rebinde vers un mapping different.

## 10. Runtime PAPER

LOT-06.3 introduit :

~~~text
IBKRRuntimeContractDetailsClient
build_ibkr_contract_reference_resolver
~~~

Le client utilise la session deja ouverte par :

~~~text
IBKRPaperConnectionRuntime
~~~

Le client brut ib_async reste dans la boundary IBKR.

## 11. Safe PAPER probe

Le script :

~~~text
scripts/probe_ibkr_paper_contract_resolution.py
~~~

permet de verifier une vraie resolution PAPER.

Entrees requises :

~~~text
--contract-id
--symbol
--instrument-id
--output
~~~

La connexion utilise les variables LOT-06.1 existantes.

Le probe :

~~~text
connects to IB Gateway PAPER
calls reqContractDetails
normalizes one exact mapping
writes sanitized JSON evidence
disconnects
~~~

Il ne place et n'annule aucun ordre.

## 12. Qualification

Le gate deterministe prouve :

~~~text
conId-based request semantics
exact conId + symbol matching
canonical InstrumentId requirement
ContractDetails normalization
market-rule preservation
SMART routing preservation
primaryExchange preservation
zero provider defaults -> unknown
no economic write
real PAPER provider proof = false
PAPER certification claim = false
LIVE = false
~~~

## 13. Provider sources

Sources verifiees le 2026-10-23 :

~~~text
ib_async 2.1.0 API docs
IBKR Requesting Contract Details
IBKR ContractDetails reference
IBKR Minimum Price Increment
~~~

## 14. Next

~~~text
LOT-06.4
IBKR Request/Callback Correlation & Order Session Sequencing Runtime
~~~

Le prochain sous-lot doit relier nextValidId, clientId, orderId, permId, orderRef et les callbacks provider avant toute admission d'un vrai economic write.
