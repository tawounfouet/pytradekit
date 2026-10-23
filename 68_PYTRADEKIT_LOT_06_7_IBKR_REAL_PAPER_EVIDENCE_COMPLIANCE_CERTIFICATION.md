# 68 - PyTradeKit - LOT-06.7 IBKR Real PAPER Evidence & Compliance Certification

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b8  
**LOT :** LOT-06.7  
**Date :** 2026-10-23  

## 1. Objectif

LOT-06.7 relie l'adapter IBKR au harness de compliance commun et introduit un contrat de preuve reelle PAPER.

Le lot distingue strictement :

~~~text
deterministic qualification
-> C2

retained real PAPER evidence
-> capability-specific C3
~~~

Aucune capability ne devient C3 par simple declaration.

## 2. Baseline certification

Sans preuve provider reelle :

~~~text
all declared IBKR capabilities
-> C2_INTEGRATION_QUALIFIED
~~~

Cette baseline repose sur les lots LOT-05.1 a LOT-06.6 et leurs gates deterministes.

## 3. C3 promotion rule

Une capability ne peut devenir C3 que si :

~~~text
capability explicitly listed in c3_capabilities
+
required PAPER gates PASS
+
capability proof fields satisfy the contract
+
SDK version matches ib_async 2.1.0
+
evidence qualified_commit matches certification target
+
artifact provenance contains SHA-256
~~~

Sinon la capability reste C2.

## 4. Evidence bundle

Le format IBKRPaperEvidenceBundle contient :

~~~text
schema_version
provider = ibkr
environment = PAPER
provenance
captured_at
sdk
masked account
release_ready
controlled_probe_passed
gates
c3_capabilities
proofs
~~~

Le compte complet n'est jamais conserve dans l'artefact.

## 5. Evidence provenance

La provenance contient :

~~~text
qualified_commit
artifact_name
artifact_json_sha256
source_ref
workflow_run_id optional
artifact_id optional
~~~

Le SHA-256 lie le bundle de certification a la source de qualification.

## 6. Capability-specific PAPER evidence

Les capabilities supportees par le contrat C3 sont :

~~~text
ACCOUNT_QUERY
ORDER_QUERY
MARKET_ORDER
LIMIT_ORDER
CANCEL_ORDER
PARTIAL_FILL
POSITION_QUERY
BALANCE_QUERY
CLIENT_ORDER_REFERENCE
EXECUTION_FACTS
RECONNECT_RECOVERY
~~~

Mais aucune n'est pre-certifiee.

PARTIAL_FILL exige une vraie execution partielle observee avec execId distincts.

RECONNECT_RECOVERY exige une vraie reconciliation fraiche et une preuve de non-replay economique.

## 7. Controlled PAPER probe

Le script :

~~~text
scripts/ibkr_paper_controlled_probe.py
~~~

peut creer des ordres PAPER uniquement avec :

~~~text
--with-orders
+
PYTRADEKIT_IBKR_ORDER_PROBE_ACK=
I_UNDERSTAND_IBKR_PAPER_ORDERS_WILL_BE_CREATED
~~~

Il n'existe aucun mode LIVE.

Le probe execute un scenario borne :

~~~text
PAPER startup
-> exact conId + symbol qualification
-> account/balance observation
-> baseline position
-> MARKET submit exactly once
-> permId + execId observation
-> LIMIT validation
-> LIMIT submit exactly once
-> cancel exactly once
-> cleanup position
-> evidence bundle
~~~

## 8. LIMIT price requirement

Le LIMIT price est fourni explicitement au probe.

Il est valide avant placeOrder avec :

~~~text
static tick
or
reqMarketRule dynamic increment
~~~

Le probe ne remplace jamais une market rule dynamique par minTick.

## 9. Cleanup

Le probe compare la position finale a la position de depart.

Si une position supplementaire a ete creee, un MARKET inverse de cleanup est emis.

Le gate paper_cleanup ne passe que si la position de depart est restauree.

## 10. Real PAPER workflow

Le workflow manuel :

~~~text
.github/workflows/ibkr-real-paper.yml
~~~

utilise :

~~~text
workflow_dispatch
self-hosted linux runner
label ibkr-paper
IB Gateway PAPER on 127.0.0.1:4002
explicit acknowledgement input
expected PAPER account secret
~~~

La CI standard n'appelle jamais ce workflow ni le probe reel.

## 11. Certification replay

Le script :

~~~text
scripts/qualify_ibkr_0_8_compliance.py
~~~

sans --paper-evidence produit une matrice C2 uniquement.

Avec --paper-evidence, il rejoue le bundle via ComplianceHarness et promeut uniquement les claims C3 valides.

## 12. Current release status

0.8.0b8 signifie :

~~~text
IBKR compliance harness implemented
deterministic C2 qualification implemented
real PAPER capture workflow implemented
retained C3 evidence not yet executed in this repository state
TRADING_READY remains closed
LIVE remains unavailable
~~~

## 13. Next

Apres une execution reelle PAPER reussie, le prochain jalon est :

~~~text
0.8.0rc1
IBKR PAPER Certified Candidate
~~~

Ce jalon devra geler le bundle retenu, publier la matrice C3 effectivement observee et reevaluer le startup trading readiness.
