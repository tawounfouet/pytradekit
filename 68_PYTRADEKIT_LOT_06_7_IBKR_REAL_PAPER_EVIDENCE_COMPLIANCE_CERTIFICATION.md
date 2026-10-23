# 68 - PyTradeKit - LOT-06.7 IBKR Real PAPER Evidence & Compliance Certification

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b8  
**LOT :** LOT-06.7  
**Date :** 2026-10-23

## 1. Objectif

LOT-06.7 construit le dernier maillon avant la promotion IBKR PAPER qualifiee :

~~~text
real provider run
-> sanitized probe
-> SHA-256 provenance
-> retained evidence bundle
-> common ComplianceHarness
-> capability certification matrix
~~~

Le lot ne fabrique aucune preuve C3 dans la CI deterministe.

## 2. Separation des environnements

~~~text
CI deterministe
-> C2 maximum

manual real PAPER workflow
-> real provider evidence
-> C3 possible capability by capability
~~~

Le workflow reel est workflow_dispatch uniquement.

## 3. Runner

Le runtime IBKR reste verrouille sur 127.0.0.1:4002.

La qualification reelle utilise donc un runner self-hosted Linux portant le label :

~~~text
pytradekit-ibkr-paper
~~~

IB Gateway PAPER doit deja etre lance localement sur ce runner.

Aucun tunnel reseau ou fallback LIVE n'est introduit.

## 4. Explicit economic-write acknowledgement

Le probe reel refuse tout ordre tant que :

~~~text
PYTRADEKIT_IBKR_ORDER_PROBE_ACK
=
I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED
~~~

n'est pas defini exactement.

## 5. Controlled PAPER scenario

Le probe execute la sequence suivante :

~~~text
PAPER startup
-> account preflight
-> conId + symbol contract qualification
-> baseline position
-> MARKET BUY
-> openOrder / orderStatus / execDetails evidence
-> order query
-> dynamic market-rule LIMIT
-> CANCEL
-> MARKET SELL cleanup
-> baseline position restored
-> disconnect
-> reconnect
-> account query
-> prove no economic replay
~~~

## 6. MARKET proof

MARKET_ORDER C3 exige :

~~~text
submitted = true
submit_attempts = 1
filled = true
perm_id_present = true
exec_id_present = true
~~~

Aucune seconde soumission n'est autorisee.

## 7. LIMIT proof

LIMIT_ORDER C3 exige :

~~~text
submitted = true
submit_attempts = 1
limit_price_present = true
market_rule_checked = true
~~~

Le prix LIMIT est fourni par l'operateur et doit rester passif pour le scenario CANCEL.

## 8. CANCEL proof

CANCEL_ORDER C3 exige exactement une tentative de cancel et une observation terminale Cancelled ou ApiCancelled.

## 9. Callback and execution proof

Le harness observe :

~~~text
openOrderEvent
orderStatusEvent
execDetailsEvent
~~~

EXECUTION_FACTS exige un execId provider, un permId, une quantite de fill positive et au moins un execDetails.

Les identifiants provider ne sont pas serialises dans l'artefact conserve.

## 10. Account, balance and position proof

ACCOUNT_QUERY et BALANCE_QUERY utilisent des accountValues scopes sur le compte attendu.

Les preuves conservees sont uniquement des booleens de presence et de readiness.

POSITION_QUERY exige une baseline observee puis restauree apres cleanup.

## 11. Reconnect proof

Le probe arrete la connexion PAPER puis la redemarre.

Le reconnect est valide si :

~~~text
disconnect observed
new startup ready
post-reconnect account query succeeds
no new qualification orderRef appears
~~~

Le reconnect ne rejoue aucune intention economique.

## 12. PARTIAL_FILL

PARTIAL_FILL reste C2.

Un fill complet ne constitue jamais une preuve de partial fill.

Une promotion C3 future exigera un vrai partial fill observe et retenu.

## 13. Evidence provenance

Le probe sanitise produit un JSON sans secret.

Le normalizer ajoute :

~~~text
source_release
qualified_commit
workflow_run_id
deterministic_ci_run_id
artifact_name
probe JSON SHA-256
~~~

Le bundle normalise devient l'unique source acceptee par le replay de certification.

## 14. Commit-linked CI

Le workflow PAPER exige un CI run ID.

Il verifie via GitHub Actions API que :

~~~text
workflow name = CI
conclusion = success
head_sha = qualification commit
~~~

Une preuve provider ne peut donc pas etre rattachee a un autre commit.

## 15. Certification levels

Sans provider reel :

~~~text
all declared IBKR capabilities = C2 maximum
~~~

Avec preuve reelle complete :

~~~text
ACCOUNT_QUERY            C3
ORDER_QUERY              C3
MARKET_ORDER             C3
LIMIT_ORDER              C3
CANCEL_ORDER             C3
POSITION_QUERY           C3
BALANCE_QUERY            C3
CLIENT_ORDER_REFERENCE   C3
EXECUTION_FACTS          C3
RECONNECT_RECOVERY       C3
PARTIAL_FILL             C2
~~~

Le moteur derive la matrice de la preuve retenue. Une preuve incomplete laisse automatiquement la capability concernee a C2.

## 16. Repository evidence policy

0.8.0b8 ne commit aucune fausse preuve IBKR PAPER.

Le repertoire retained evidence reste vide jusqu'a un vrai run manuel.

## 17. Promotion gate

Le workflow reel execute :

~~~text
qualify_ibkr_real_paper.py
-> normalize_ibkr_paper_evidence.py
-> qualify_ibkr_0_8_certification.py --require-c3-target
~~~

Le dernier step echoue si une capability C3 eligible reste sous C3.

## 18. Certification status

Sur le commit 0.8.0b8 deterministe :

~~~text
real PAPER evidence bundled = false
C3 claim = false
TRADING_READY certification = false
LIVE = false
~~~

## 19. Next

Apres un vrai run PAPER complet et la retention de son artefact, le prochain jalon recommande est :

~~~text
0.8.0rc1
IBKR PAPER Qualified Release Candidate
~~~
