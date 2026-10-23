# 62 - PyTradeKit - LOT-06.1 IBKR Transport Selection & PAPER Connection Runtime

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b2  
**LOT :** LOT-06.1  
**Date :** 2026-10-23  

## 1. Objectif

LOT-06.1 introduit le premier transport provider reel selectionne pour IBKR sans encore produire de preuve economique PAPER.

Le sous-lot couvre :

~~~text
transport selection
provider-local runtime profile
IB Gateway PAPER connection
protocol readiness
nextValidId readiness
account identity verification
sanitized startup report
safe manual PAPER connection probe
~~~

Il ne couvre pas encore :

~~~text
MARKET order submission
LIMIT order submission
CANCEL
execution mapping from real provider callbacks
real PAPER C3 certification
LATEST_QUOTE certification
LIVE
~~~

## 2. Transport selectionne

Le transport retenu est :

~~~text
ib_async==2.1.0
~~~

Il reste une dependance optionnelle :

~~~text
pip install -e ".[ibkr]"
~~~

Le core PyTradeKit ne depend pas de ib_async.

Le package est charge uniquement dans :

~~~text
pytradekit.brokers.adapters.ibkr
~~~

## 3. Pourquoi ib_async

LOT-04 avait differe le SDK officiel IBKR 10.49+ en raison du changement de licence documente par IBKR.

ib_async fournit :

~~~text
BSD-2-Clause
Python 3.12 support
TWS / IB Gateway socket protocol
connection synchronization
managed accounts
order, position and execution state
~~~

La selection du transport ne modifie aucun contrat canonique.

## 4. Runtime profile

LOT-06.1 introduit :

~~~text
IBKRPaperRuntimeProfile
~~~

Valeurs qualifiees :

~~~text
provider = ibkr
environment = PAPER
host = 127.0.0.1
port = 4002
client_id = 1 by default
transport = ib_async==2.1.0
~~~

## 5. Loopback only

Le premier runtime est volontairement limite a :

~~~text
127.0.0.1
localhost
~~~

Une IP distante est rejetee.

Cette contrainte reduit la surface de configuration avant la qualification PAPER complete.

## 6. PAPER endpoint hard lock

Le runtime reutilise la validation LOT-04.

~~~text
IB Gateway PAPER = 4002
~~~

Les ports LIVE restent rejetes.

Aucun fallback LIVE n'existe.

## 7. Client ID policy

Le runtime LOT-06.1 interdit :

~~~text
clientId = 0
~~~

Raison :

~~~text
clientId 0
-> automatic manual-order binding behavior in ib_async / TWS order management
~~~

Or LOT-04 a explicitement classe l'adoption automatique des ordres TWS manuels hors scope.

Le default devient donc :

~~~text
clientId = 1
~~~

Il reste configurable avec une valeur non nulle.

## 8. Connection contract

IBAsyncPaperTransport utilise :

~~~text
host
port
clientId
timeout
readonly = false
account = expected PAPER account
raiseSyncErrors = true
~~~

Le transport exige ensuite :

~~~text
isConnected() = true
client.isReady() = true
expected account in managedAccounts()
~~~

## 9. nextValidId readiness

ib_async ne retourne la connexion comme prete qu'apres synchronisation du client.

LOT-06.1 utilise :

~~~text
client.isReady()
~~~

comme preuve transport que le handshake incluant nextValidId a ete termine.

Aucun orderId n'est fabrique par PyTradeKit.

## 10. Account identity

Le runtime possede :

~~~text
expected_account_id
~~~

La connexion est rejetee si ce compte n'apparait pas dans :

~~~text
managedAccounts()
~~~

Le compte complet n'apparait jamais dans les diagnostics de startup.

## 11. Startup readiness

Le runtime produit :

~~~text
StartupReadinessReport
~~~

avec les checks :

~~~text
profile
transport_package
paper_endpoint
socket
protocol
provider_account
~~~

Un report PASS signifie uniquement :

~~~text
READY_FOR_STARTUP
~~~

Il ne signifie jamais :

~~~text
TRADING_READY
C3 PAPER QUALIFIED
~~~

## 12. Failure semantics

Connection refused, timeout ou erreur transport :

~~~text
ProviderUnavailableError
~~~

Protocol handshake incomplet ou account mismatch :

~~~text
ProviderProtocolError
~~~

Les messages d'exception provider ne sont pas recopies bruts dans les diagnostics.

## 13. Safe real PAPER probe

Le script :

~~~text
scripts/probe_ibkr_paper_connection.py
~~~

peut connecter un IB Gateway PAPER reel.

Il :

~~~text
connecte
verifie le handshake
verifie le compte
capture une preuve sanitisee
se deconnecte
~~~

Il ne :

~~~text
place aucun ordre
cancel aucun ordre
modifie aucune position
declare aucune certification
~~~

## 14. Fitness functions

~~~text
FF-145 ib_async is optional and exactly pinned.
FF-146 official ibapi remains absent.
FF-147 IBKR transport stays inside the provider adapter boundary.
FF-148 Alpaca RuntimeProfile remains unchanged.
FF-149 IBKR runtime types do not enter canonical layers.
FF-150 IB Gateway PAPER port 4002 remains hard locked.
FF-151 LIVE ports remain unavailable.
FF-152 runtime host is loopback only.
FF-153 clientId 0 is rejected.
FF-154 synchronized protocol readiness is required.
FF-155 expected PAPER account identity is required.
FF-156 connection exceptions are sanitized.
FF-157 startup readiness does not claim trading readiness.
FF-158 deterministic qualification does not claim real PAPER evidence.
~~~

## 15. Sources

Provider and transport sources checked on 2026-10-23:

~~~text
Interactive Brokers TWS API connection documentation
Interactive Brokers nextValidId readiness documentation
Interactive Brokers PAPER port documentation
ib_async 2.1.0 API documentation
ib_async BSD-2-Clause license
~~~

## 16. Resultat

LOT-06.1 prouve :

~~~text
PyTradeKit
-> provider-local IBKR runtime
-> ib_async 2.1.0
-> IB Gateway PAPER 4002
-> synchronized socket
-> expected account identity
-> READY_FOR_STARTUP
~~~

sans encore produire un effet economique.

## 17. Next

~~~text
LOT-06.2
IBKR Read-Side Snapshot Adapter & Startup Reconciliation
~~~

Ce prochain sous-lot doit connecter les observations reelles :

~~~text
account values
positions
open orders
executions
~~~

aux mappings SDK-free de LOT-05, puis construire la reconciliation initiale avant toute admission d'ordre.
