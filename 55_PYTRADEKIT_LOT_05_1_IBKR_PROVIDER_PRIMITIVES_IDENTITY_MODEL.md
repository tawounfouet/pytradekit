# 55 - PyTradeKit - LOT-05.1 IBKR Provider Primitives & Identity Model

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b1  
**LOT :** LOT-05.1  
**Date :** 2026-10-23  
**Statut :** implementation candidate  
**Provider :** Interactive Brokers  
**Environment :** provider-neutral ACL primitives, PAPER target

---

# 1. Objectif

LOT-05.1 est la premiere implementation de l'IBKR Anti-Corruption Layer.

Le but n'est pas encore de se connecter a IB Gateway.

Le but est de rendre explicites et typees les identites provider qui ont ete figees par LOT-04 :

~~~text
clientId
orderId
permId
orderRef
execId
conId
~~~

sans permettre a ces concepts de devenir des identifiants canoniques PyTradeKit.

# 2. Principe directeur

~~~text
provider identity
!=
canonical identity
~~~

Le core continue a manipuler :

~~~text
OrderId
FillId
InstrumentId
AccountId
~~~

L'ACL IBKR manipule :

~~~text
IBKRClientId
IBKRSessionOrderId
IBKRPermanentOrderId
IBKROrderReference
IBKRExecutionId
IBKRContractId
~~~

Les mappings sont explicites et unidirectionnels.

# 3. Order identity

Le modele IBKR doit conserver simultanement :

~~~text
clientId
+
orderId
+
orderRef
+
optional permId
~~~

Le couple clientId + orderId est une cle de routage de session.

Il ne devient jamais Order.external_order_id.

Le permId non nul est le seul candidat LOT-05.1 pour ProviderOrderIdentity.external_order_id.

# 4. Pending permanent identity

Le provider peut etre observe avant que le permId stable ne soit disponible.

Le modele autorise donc une IBKROrderIdentity dont permanent_order_id vaut None, mais interdit la conversion vers ProviderOrderIdentity tant qu'un permId non nul n'a pas ete observe.

Cela evite de fabriquer une identite durable a partir de orderId.

# 5. Immutable permId binding

~~~text
None -> permId
allowed

permId X -> permId X
idempotent

permId X -> permId Y
rejected
~~~

# 6. orderRef

orderRef est represente par IBKROrderReference.

Il sert de correlation provider avec le client reference PyTradeKit.

Il n'est pas un OrderId.

# 7. Execution identity

Chaque observation d'execution IBKR utilise IBKRExecutionId et se traduit vers ProviderFillIdentity.external_fill_id.

LOT-05.1 ne cree pas encore de Fill.

Il ne fait que representer l'identite de l'observation provider.

# 8. Execution corrections

Une correction d'execution peut produire un nouvel execId partageant la meme famille avec une revision finale differente.

LOT-05.1 introduit donc IBKRExecutionCorrection.

Important :

~~~text
syntactic correction candidate
!=
economic correction proven
~~~

Le mapper LOT-05.5 / LOT-05.6 devra egalement verifier que les autres champs provider correspondent avant de conclure qu'il s'agit d'une correction.

# 9. Contract identity

Un contrat IBKR qualifie utilise conId, represente par IBKRContractId et IBKRContractIdentity.

La conversion IBKRContractIdentity vers ProviderInstrumentIdentity reste externe au Domain.

Le mapping complet Contract vers Instrument appartient a LOT-05.2.

# 10. Connection identity

clientId est represente par IBKRClientId et IBKRConnectionIdentity.

Il est strictement runtime-local.

Il ne devient ni AccountId, ni OrderId, ni CorrelationId.

# 11. Order identity registry

LOT-05.1 introduit un registre runtime provider-specific : IBKROrderIdentityRegistry.

Index :

~~~text
(clientId, orderId)
orderRef
permId
~~~

Le registre autorise qu'un meme permId soit observe sous une nouvelle cle de routage apres changement de session, tant que la correlation orderRef reste coherente.

Il rejette :

~~~text
same route -> conflicting orderRef
same orderRef -> conflicting permId
same permId -> conflicting orderRef
~~~

# 12. Conversion vers les modeles provider-neutral

~~~text
IBKROrderReference
-> ProviderOrderIdentity.client_reference

IBKRPermanentOrderId
-> ProviderOrderIdentity.external_order_id

IBKRExecutionId
-> ProviderFillIdentity.external_fill_id

IBKRContractId
-> ProviderInstrumentIdentity.external_id
~~~

Aucune modification de ces modeles generiques n'est requise.

# 13. Scope explicitement hors LOT-05.1

~~~text
ib_async dependency
ibapi dependency
network connection
IB Gateway runtime
placeOrder
cancelOrder
openOrder mapping
orderStatus mapping
account mapping
balance mapping
position mapping
pacing mapper
timestamp normalization
real PAPER evidence
CertifiedCapability
~~~

# 14. Fitness functions

~~~text
FF-071 IBKR SDK imports remain absent from the identity model.
FF-072 clientId never becomes canonical identity.
FF-073 orderId never becomes ProviderOrderIdentity.external_order_id.
FF-074 ProviderOrderIdentity requires non-zero permId.
FF-075 permId cannot be silently rebound.
FF-076 execId maps to ProviderFillIdentity without creating a Fill.
FF-077 correction relation is explicit and provider-local.
FF-078 conId remains provider instrument identity.
FF-079 IBKR identity types do not leak into canonical layers.
FF-080 generic provider identity models remain IBKR-free.
~~~

# 15. Gate LOT-05.1

~~~text
typed provider primitives PASS
order identity layering PASS
pending permId behavior PASS
identity registry conflicts PASS
execution correction identity PASS
conId mapping PASS
public contract PASS
architecture isolation PASS
mypy PASS
Ruff PASS
full suite PASS
release artifacts PASS
~~~

# 16. Resultat attendu

~~~text
IBKR has richer identity semantics than Alpaca
and
PyTradeKit can preserve them without changing canonical IDs
~~~

Le resultat n'est pas encore IBKR execution works.

# 17. Prochaine etape

~~~text
LOT-05.2
IBKR Contract & Instrument Mapping
~~~

Le prochain sous-lot devra transformer les objets contrats IBKR en observations provider-neutral sans faire entrer Contract, Stock, Forex ou d'autres types SDK dans le core.
