# 45 - PyTradeKit - Alpaca Controlled PAPER Order Probe

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-04F - Alpaca Controlled PAPER Order Probe`  
**Date :** 2026-10-22  
**Statut :** Implemented harness - real PAPER execution requires user credentials and explicit acknowledgement  
**SDK qualifie :** `alpaca-py==0.44.0`

---

## 1. Objectif

Ce lot introduit les premieres operations economiques controlees contre Alpaca PAPER.

Il qualifie :

```text
MARKET
LIMIT
CANCEL
client_order_id
trade_updates
single-attempt command transport
UNCERTAIN recovery
cleanup
```

Le but n'est toujours pas de produire l'adapter Alpaca final.

Le but est de produire une preuve executable que PyTradeKit peut :

```text
create one intended PAPER order
avoid implicit transport resubmission
lose the apparent response
recover by client_order_id
observe execution state
cancel a non-marketable limit order
restore the initial simulated position
```

---

## 2. Position dans la roadmap

```text
39 - Alpaca API & SDK Integration Analysis
DONE

40 - Binance Spot API & SDK Integration Analysis
DONE

41 - IBKR API & SDK Integration Analysis
DONE

42 - Pepperstone + cTrader API & SDK Integration Analysis
DONE

43 - Provider Comparative Architecture
DONE

44 - Alpaca PAPER Read-Only Probe Harness
DONE

45 - Alpaca Controlled PAPER Order Probe
THIS LOT

46 - Alpaca Integration Contract Freeze
NEXT

LOT-05 - PAPER Runtime Configuration
LATER
```

---

## 3. Safety model

Le probe est :

```text
PAPER ONLY
EXPLICITLY OPT-IN
EXPECTED ACCOUNT REQUIRED
MARKET MUST BE OPEN
SMALL MARKET QUANTITY
LIMIT FAR BELOW CURRENT BID
SINGLE TRANSPORT ATTEMPT
NO LIVE SELECTOR
NO LIVE FALLBACK
```

Le probe peut creer des ordres uniquement dans l'environnement PAPER.

Il ne propose aucun argument CLI permettant de selectionner LIVE.

---

## 4. Explicit acknowledgement

Avant toute operation d'ecriture, la variable suivante est obligatoire :

```text
PYTRADEKIT_ALPACA_ORDER_PROBE_ACK
```

Sa valeur doit etre exactement :

```text
I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED
```

Sans cette valeur :

```text
FAIL CLOSED
```

---

## 5. Expected account identity

Le write probe exige aussi :

```text
PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID
```

Contrairement au probe 44, cette valeur n'est pas optionnelle.

Raison :

```text
read-only wrong account
= diagnostic problem

write wrong account
= safety problem
```

Si l'identite retournee par Alpaca ne correspond pas :

```text
no order is created
```

---

## 6. Credentials

Variables :

```text
PYTRADEKIT_ALPACA_PAPER_API_KEY
PYTRADEKIT_ALPACA_PAPER_SECRET_KEY
```

Les secrets :

```text
do not appear in CLI arguments
do not appear in report
do not appear in repr(config)
do not appear in fixtures
```

---

## 7. Command-side retry problem

`alpaca-py==0.44.0` repose sur `RESTClient`.

Le comportement par defaut du SDK est :

```text
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_WAIT_SECONDS = 3
DEFAULT_RETRY_EXCEPTION_CODES = [429, 504]
```

Cette policy s'applique au transport REST generique.

Elle peut donc affecter :

```text
POST /orders
```

et d'autres operations economiques.

---

## 8. Critical invariant

PyTradeKit impose :

```text
one canonical submit command
must not accidentally become
multiple provider order submissions
```

Donc :

```text
default SDK command retry
```

n'est pas acceptable pour le command path.

---

## 9. Separate read and command clients

Le lot 45 utilise deux clients Trading API distincts.

```text
read_client
    |
    +-- account
    +-- clock
    +-- asset
    +-- positions
    +-- order query
    +-- get_order_by_client_id

command_client
    |
    +-- submit MARKET
    +-- submit LIMIT
    +-- cancel
```

Le read client conserve le comportement read-side du SDK.

Le command client neutralise les retries.

---

## 10. AlpacaSingleAttemptTradingClient

Le nouveau client :

```text
AlpacaSingleAttemptTradingClient
```

herite de :

```text
TradingClient
```

et force :

```python
self._retry = 0
```

apres initialisation.

---

## 11. Why a private SDK field is used

`TradingClient.__init__` dans `alpaca-py==0.44.0` n'expose pas les options :

```text
retry_attempts
retry_wait_seconds
retry_exception_codes
```

bien que son parent `RESTClient` les expose.

Le probe utilise donc temporairement :

```text
self._retry = 0
```

comme mecanisme de qualification.

---

## 12. This is not the final production transport

L'utilisation de :

```text
RESTClient._retry
```

est une dependance sur un detail interne du SDK.

Le lot 46 devra decider si le runtime final utilise :

```text
A. this pinned SDK behavior

B. a safer wrapper around RESTClient internals

C. a dedicated command HTTP transport

D. another proven mechanism
```

---

## 13. One explicit submit call

Le method :

```text
submit_once()
```

contient exactement :

```text
one call to submit_order()
```

Les architecture tests verifient cette propriete.

---

## 14. One explicit cancel call

Le method :

```text
cancel_once()
```

contient exactement :

```text
one call to cancel_order_by_id()
```

Aucun retry applicatif n'est ajoute.

---

## 15. client_order_id

Chaque order du probe possede une reference unique.

Format :

```text
PTK45-MKT-...
PTK45-LMT-...
PTK45-CLEAN-...
```

Ces references sont generees avant submission.

---

## 16. Why client_order_id matters

Alpaca permet de retrouver un order avec :

```text
GET /v2/orders:by_client_order_id
```

Le lot 45 utilise cette operation comme primitive de recovery.

---

## 17. MARKET uncertain recovery rehearsal

Le premier MARKET order utilise une technique volontaire.

Flow :

```text
build client_order_id
        |
        v
submit exactly once
        |
        v
Alpaca returns success
        |
        v
probe intentionally discards response
        |
        v
raise AlpacaSimulatedResponseLoss
        |
        v
state = UNCERTAIN
        |
        v
query by client_order_id
        |
        v
recover provider order
        |
        v
NO RESUBMIT
```

---

## 18. Why simulate response loss after provider ACK

Cette technique permet de tester en vrai PAPER le cas le plus important :

```text
remote side effect exists
but caller cannot use original response
```

sans devoir provoquer artificiellement :

```text
network packet loss
proxy failure
TCP reset
```

---

## 19. What this proves

Cela prouve :

```text
client reference exists before submission
one network submit attempt
recovery query works
provider order identity is recoverable
no second submit is required
```

---

## 20. What this does not prove

Cela ne prouve pas encore :

```text
actual packet-loss behavior
actual 504 after provider acceptance
actual process crash between send and persistence
actual OS socket failure
```

Ces scenarios appartiennent a une qualification plus profonde.

---

## 21. ExecutionCertainty

Le report note :

```text
certainty_before_recovery = UNCERTAIN
```

puis :

```text
recovered order
```

Le probe ne pretend pas qu'une exception transport signifie :

```text
FAILED
```

---

## 22. Recovery metadata

Le report capture :

```text
trigger
client_order_id
recovery_queries
recovered_order_id
recovered_status
submit_attempts
resubmitted
```

La valeur attendue :

```text
resubmitted = false
```

---

## 23. MARKET order quantity

Default :

```text
0.001 share
```

pour un asset fractionable.

Cela limite l'effet economique meme en PAPER.

---

## 24. Asset checks

Avant submit :

```text
asset.tradable == true
```

est exige.

Si la quantite est fractionnaire :

```text
asset.fractionable == true
```

est egalement exige.

---

## 25. Provider quantity constraints

Le probe verifie lorsque disponibles :

```text
min_order_size
min_trade_increment
```

La quantite MARKET doit respecter ces contraintes.

---

## 26. Market-open gate

Le probe exige :

```text
clock.is_open == true
```

avant le premier order.

Raison :

```text
MARKET order qualification
```

doit observer un cycle actif plutot qu'un order simplement queued pour le prochain open.

---

## 27. Latest quote

Le probe charge une quote juste avant les ordres.

Default feed :

```text
IEX
```

---

## 28. LIMIT order objective

Le LIMIT order sert principalement a qualifier :

```text
submit
provider order ID
client_order_id
cancel
cancel state convergence
```

Il n'est pas destine a etre execute.

---

## 29. Limit quantity

Default :

```text
1 full share
```

Raison :

la documentation du SDK reste plus restrictive sur les fractional quantities pour les LIMIT orders que pour MARKET.

---

## 30. Safe non-marketable price

Le LIMIT BUY est calcule a partir du bid courant.

Default :

```text
5000 basis points below current bid
```

soit environ :

```text
50 percent below bid
```

puis aligne sur :

```text
asset.price_increment
```

---

## 31. Configurable discount

Variable :

```text
PYTRADEKIT_ALPACA_ORDER_PROBE_LIMIT_DISCOUNT_BPS
```

Default :

```text
5000
```

Bornes :

```text
100 <= discount <= 9000
```

---

## 32. Why BUY limit

Le probe utilise :

```text
BUY LIMIT far below market
```

plutot qu'un SELL LIMIT sans inventaire.

Cela evite d'introduire volontairement un short order.

---

## 33. CANCEL

Apres acceptance du LIMIT :

```text
one cancel request
```

est envoye.

Aucun retry applicatif n'est execute si le cancel transport echoue.

---

## 34. Cancel uncertainty

En cas d'exception du cancel :

```text
cancel result = UNCERTAIN
```

puis le probe continue a observer l'order par query.

Il ne rappelle pas automatiquement :

```text
cancel_order_by_id
```

---

## 35. Cancel-fill race

Le LIMIT est tres loin du marche, mais le probe ne suppose pas que fill est impossible.

Le final order peut etre :

```text
CANCELED
FILLED
EXPIRED
REJECTED
```

Le result ideal attendu est :

```text
CANCELED
```

---

## 36. Filled quantity accounting

Le probe additionne toute quantite BUY effectivement filled par :

```text
MARKET
+
LIMIT if unexpected partial/full fill
```

Cette quantite est ensuite utilisee pour le cleanup.

---

## 37. Cleanup

Le probe tente de revenir a la position de depart.

Si le probe a achete :

```text
x
```

shares, il soumet :

```text
SELL MARKET x
```

en PAPER.

---

## 38. Cleanup also uses single-attempt command transport

Le cleanup passe par le meme :

```text
AlpacaSingleAttemptTradingClient
```

Donc :

```text
SDK automatic retries = 0
```

reste vrai.

---

## 39. Cleanup uncertainty

Si la reponse du cleanup est incertaine :

```text
query by client_order_id
```

est utilise.

Aucun blind resubmit.

---

## 40. Position baseline

Avant les operations :

```text
baseline_position_qty
```

est capture.

---

## 41. Final position

Apres cleanup :

```text
final_position_qty
```

est recharge.

Le resultat ideal :

```text
final_position_qty == baseline_position_qty
```

---

## 42. Existing position support

Le probe ne suppose pas necessairement une position initiale nulle.

Il mesure le delta.

Exemple :

```text
baseline = 10
market BUY 0.001
cleanup SELL 0.001
final = 10
```

---

## 43. Existing short position

Meme principe conceptuel :

```text
baseline = -5
market BUY 0.001
cleanup SELL 0.001
final = -5
```

---

## 44. Error path safety

Si une submission devient vraiment unresolved :

```text
client_order_id query timeout
```

le probe ne resoumet pas.

Il produit :

```text
FAIL
```

et demande inspection du compte PAPER.

---

## 45. Why no blind cleanup for unknown side effect

Un order unresolved peut avoir :

```text
executed
not executed
partially executed
```

Creer un autre order pour "annuler" un effet inconnu peut aggraver la situation.

La seule voie correcte est :

```text
reconciliation
```

---

## 46. Stream capture

Le probe ouvre :

```text
TradingStream(paper=True)
```

avant les ordres.

Il collecte :

```text
trade_updates
```

pendant la sequence.

---

## 47. Expected stream events

Selon timing et provider simulation :

```text
new
accepted
partial_fill
fill
pending_cancel
canceled
```

peuvent apparaitre.

Le probe n'exige pas un ordre exact de tous ces events pour PASS.

---

## 48. Why stream is observational

La verite de convergence du probe repose actuellement sur :

```text
REST query by client_order_id
```

Le stream sert de preuve complementaire.

Le futur adapter combinera :

```text
stream facts
+
snapshot/reconciliation
```

---

## 49. Stream warmup

Default :

```text
2 seconds
```

avant le premier submit.

Variable :

```text
PYTRADEKIT_ALPACA_ORDER_PROBE_STREAM_WARMUP_SECONDS
```

---

## 50. Stream tail

Default :

```text
2 seconds
```

apres les operations.

Variable :

```text
PYTRADEKIT_ALPACA_ORDER_PROBE_STREAM_TAIL_SECONDS
```

---

## 51. Polling

Order queries utilisent un polling borne.

Defaults :

```text
timeout = 30 seconds
poll interval = 0.5 second
```

---

## 52. Poll configuration

Variables :

```text
PYTRADEKIT_ALPACA_ORDER_PROBE_TIMEOUT_SECONDS
PYTRADEKIT_ALPACA_ORDER_PROBE_POLL_SECONDS
```

---

## 53. Result PASS

Le report retourne :

```text
PASS
```

si :

```text
no recorded errors
AND
final position == baseline position
```

---

## 54. Result FAIL

Le report retourne :

```text
FAIL
```

si :

```text
order flow error
cancel result unexpected
cleanup error
position not restored
```

---

## 55. Report content

Le JSON sanitise contient :

```text
environment
sdk version target
result
masked account
preflight
market order
uncertain recovery
limit order
cancel
cleanup order
baseline position
final position
trade_updates
stream status
transport safety
warnings
errors
```

---

## 56. Transport safety evidence

Exemple :

```json
{
  "sdk_retry_attempts": 0,
  "market_submit_attempts": 1,
  "limit_submit_attempts": 1,
  "cleanup_submit_attempts": 1,
  "cancel_attempts": 1
}
```

---

## 57. Secrets absent from report

Le report ne contient pas :

```text
API key
secret key
raw authorization headers
full account ID
full account number
```

---

## 58. Account masking

Comme LOT-44 :

```text
full provider account identity
```

est masque dans le report.

---

## 59. Running the probe

Installation :

```bash
python -m pip install -e ".[alpaca]"
```

Environment :

```bash
export PYTRADEKIT_ALPACA_PAPER_API_KEY="..."
export PYTRADEKIT_ALPACA_PAPER_SECRET_KEY="..."
export PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID="..."
export PYTRADEKIT_ALPACA_ORDER_PROBE_ACK="I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED"

export PYTRADEKIT_ALPACA_ORDER_PROBE_SYMBOL="AAPL"
export PYTRADEKIT_ALPACA_DATA_FEED="iex"
```

Run :

```bash
python scripts/alpaca_paper_order_probe.py
```

---

## 60. Persist sanitized evidence

```bash
python scripts/alpaca_paper_order_probe.py \
  --output artifacts/alpaca/paper-controlled-order-probe.json
```

---

## 61. Recommended first real run

Conserver les defaults :

```text
symbol = AAPL
market qty = 0.001
limit qty = 1
limit discount = 5000 bps
```

Ne pas augmenter les quantites pour la premiere qualification.

---

## 62. Never paste credentials into chat

Les credentials PAPER doivent rester dans :

```text
local environment
secret manager
CI secret only if a future opt-in qualification workflow is created
```

---

## 63. CI policy

La CI :

```text
installs alpaca extra
imports SDK
runs unit tests
runs architecture tests
```

mais :

```text
does not set PAPER credentials
does not set acknowledgement
does not contact Alpaca
does not create PAPER orders
```

---

## 64. Unit tests

Les tests couvrent :

```text
explicit acknowledgement required
expected account required
config repr redaction
SDK retry count forced to zero
one submit attempt
simulated response loss
client_order_id recovery
MARKET fill
LIMIT submit
CANCEL
cleanup
position restoration
```

---

## 65. Architecture tests

Les fitness functions verifient :

```text
no LIVE endpoint reference
paper=True is forced
self._retry = 0 exists
submit_once contains one submit_order call
cancel_once contains one cancel_order_by_id call
```

---

## 66. Why one call AST test matters

Le test ne prouve pas tout le comportement reseau.

Mais il empeche une regression simple telle que :

```python
try:
    submit_order(...)
except:
    submit_order(...)
```

dans `submit_once`.

---

## 67. Runtime uncertainty experiment

Le lot 45 valide une forme de :

```text
post-ack response loss
```

qui est suffisante pour verifier le mecanisme de recovery.

---

## 68. Future real fault injection

LOT-46 ou la qualification finale pourra ajouter :

```text
HTTP proxy fault injection
socket reset
process crash
504 simulation
429 simulation
stream disconnect
```

sans changer la semantique du Domain.

---

## 69. Current limitation - SDK private retry field

Le mecanisme :

```text
self._retry = 0
```

est version-coupled a :

```text
alpaca-py==0.44.0
```

Cela doit etre revalide a chaque upgrade.

---

## 70. Current limitation - float request boundary

Le SDK type actuellement plusieurs fields de request comme :

```text
float
```

Le probe calcule les valeurs avec :

```text
Decimal
```

puis effectue la conversion seulement au boundary SDK.

Le Domain PyTradeKit ne doit pas adopter `float` pour ses valeurs economiques.

---

## 71. Current limitation - PAPER simulation

PAPER ne reproduit pas parfaitement :

```text
market impact
queue position
latency slippage
information leakage
```

Le probe qualifie une integration API.

Il ne qualifie pas la fidelite economique du LIVE.

---

## 72. Current limitation - market open

Le probe refuse de s'executer market closed.

Cela est volontaire.

---

## 73. Current limitation - US equity first

Le scope est :

```text
US_EQUITY
```

Le probe ne qualifie pas :

```text
options
crypto
advanced orders
brackets
OTO
OCO
```

---

## 74. Current limitation - LIMIT full share

Le LIMIT utilise une quantite full-share par prudence.

Le MARKET utilise une quantite fractionnaire.

---

## 75. No production Inbox yet

Les `trade_updates` sont captures dans le report.

Ils ne sont pas encore passes dans :

```text
Inbox
OMS
Portfolio
Outbox
PostgreSQL
```

---

## 76. No production reconciliation service yet

Le recovery est local au probe.

LOT-46 doit extraire les contrats finaux.

---

## 77. No RuntimeProfile yet

La configuration reste environment-variable driven.

LOT-05 introduira le runtime PAPER profile apres freeze du contract.

---

## 78. Critical LOT-45 invariant

Le gate principal est :

> One controlled PyTradeKit submit intent causes at most one explicit Alpaca submit call, and an uncertain result is reconciled by `client_order_id` instead of resubmission.

---

## 79. Gate code-complete

```text
[ ] PAPER-only builder
[ ] expected account mandatory
[ ] explicit write acknowledgement mandatory
[ ] market-open gate
[ ] symbol/quantity provider checks
[ ] separate read and command clients
[ ] SDK command retries forced to zero
[ ] MARKET controlled order
[ ] synthetic post-ack response loss
[ ] recovery by client_order_id
[ ] no resubmit
[ ] LIMIT far from market
[ ] CANCEL exactly once
[ ] cleanup MARKET
[ ] final position comparison
[ ] trade_updates capture
[ ] sanitized report
[ ] unit tests
[ ] architecture tests
[ ] CI remains offline from Alpaca
```

---

## 80. Real PAPER qualification gate

Le lot n'est pas provider-qualified tant qu'un vrai run n'a pas prouve :

```text
[ ] PAPER auth succeeds
[ ] expected account matches
[ ] market open
[ ] selected asset is tradable
[ ] latest quote received
[ ] MARKET submit succeeds once
[ ] synthetic response loss triggers UNCERTAIN
[ ] order recovered by client_order_id
[ ] submit count remains one
[ ] MARKET reaches FILLED
[ ] LIMIT accepted
[ ] LIMIT cancel requested once
[ ] LIMIT reaches CANCELED
[ ] cleanup reaches FILLED
[ ] final position equals baseline
[ ] useful trade_updates captured
[ ] no secrets appear in report
```

---

## 81. Failure handling

Si le report indique :

```text
FAIL
```

ne pas relancer immediatement.

D'abord inspecter :

```text
open PAPER orders
PAPER position
report errors
client_order_id values
```

puis reconciler.

---

## 82. Why immediate rerun is dangerous even in PAPER

Le but du probe est de construire une discipline reproductible.

Une habitude :

```text
failed command -> rerun everything
```

est exactement le comportement que PyTradeKit cherche a eviter avant LIVE.

---

## 83. Expected output pattern

Success :

```text
MARKET submit attempts = 1
UNCERTAIN
recovered by client_order_id
MARKET FILLED

LIMIT submit attempts = 1
LIMIT NEW
cancel attempts = 1
LIMIT CANCELED

cleanup submit attempts = 1
cleanup FILLED

baseline position == final position

PASS
```

---

## 84. Relationship with LOT-44

LOT-44 prouvait :

```text
reads
account identity
market data
stream construction
```

LOT-45 ajoute :

```text
controlled economic side effects
certainty handling
recovery
cancel
cleanup
```

---

## 85. Relationship with LOT-46

LOT-46 devra transformer les observations en contrats stables.

Il devra notamment figer :

```text
ProviderOrderIdentity mapping
ClientOrderReference mapping
Execution status mapping
TradeEvent mapping
error taxonomy
safe submit transport
cancel semantics
snapshot semantics
startup reconciliation semantics
```

---

## 86. Candidate production split after LOT-45

```text
AlpacaReadAdapter
    safe read retry

AlpacaCommandTransport
    max transport attempts = 1

AlpacaExecutionEventReceiver
    TradingStream

AlpacaReconciliationAdapter
    query by client_order_id
    query open/closed orders
    positions
```

---

## 87. Why query by client_order_id belongs to reconciliation

It answers:

```text
did the provider create the intended order?
```

without generating a new economic side effect.

---

## 88. Why cancel should also be reconciled

`cancel_order_by_id()` returning does not prove:

```text
order status == CANCELED
```

The probe therefore waits for provider state.

---

## 89. Cancel request vs cancel fact

Canonical distinction:

```text
cancel requested
!=
canceled
```

LOT-45 preserves this distinction.

---

## 90. MARKET response vs fill fact

Same distinction:

```text
submit returned
!=
filled
```

The probe polls until:

```text
FILLED
```

---

## 91. Stream fact vs snapshot

The stream is a fact channel.

REST query is a snapshot/reconciliation channel.

PyTradeKit needs both.

---

## 92. Data collected for contract freeze

After real execution, sanitize and preserve:

```text
MARKET order payload shape
LIMIT order payload shape
CANCELED order shape
trade_updates examples
client_order_id behavior
execution_id behavior
timestamps
status transitions
```

---

## 93. Fixture promotion

Potential fixtures:

```text
tests/fixtures/alpaca/
    market_order_filled.json
    limit_order_new.json
    limit_order_canceled.json
    trade_update_new.json
    trade_update_fill.json
    trade_update_canceled.json
```

Only after real PAPER observation.

---

## 94. Do not invent partial-fill fixture

Partial fills should only be marked as provider-observed if actually captured.

Synthetic unit fixtures can still test canonical logic, but must be labeled synthetic.

---

## 95. Request IDs

If accessible from the final command transport, Alpaca request IDs should be captured as infrastructure diagnostics.

They are not canonical order identity.

---

## 96. SDK deprecation warning

LOT-44 observed the SDK dependency on:

```text
websockets.legacy
```

The warning remains a provider SDK qualification item.

It does not affect the core Domain.

---

## 97. Upgrade policy

Before moving beyond `alpaca-py==0.44.0`:

```text
recheck REST retry internals
recheck TradingClient constructor
recheck TradingStream behavior
recheck client_order_id lookup
rerun LOT-44
rerun LOT-45
```

---

## 98. Security principle

PAPER is safer than LIVE but it must still be treated with production-style discipline.

The objective is to validate:

```text
correct control behavior
```

before real capital exists.

---

## 99. Final decision

LOT-45 establishes the first controlled write path for PyTradeKit.

Its most important result is not simply:

```text
we can place an Alpaca order
```

The important result is:

```text
we can place exactly one intended order,
lose confidence in the response,
recover state without resubmitting,
cancel a controlled order,
and restore the PAPER account position.
```

---

## 100. Next

After one successful real PAPER run and fixture capture:

```text
46_PYTRADEKIT_ALPACA_INTEGRATION_CONTRACT_FREEZE.md
```

should freeze the Alpaca adapter contract before LOT-05.

---

## 101. Official references

```text
https://docs.alpaca.markets/us/reference/postorder
https://docs.alpaca.markets/us/reference/getorderbyclientorderid
https://docs.alpaca.markets/us/docs/orders-at-alpaca
https://docs.alpaca.markets/us/docs/paper-trading
https://github.com/alpacahq/alpaca-py
```

---

## 102. Final principle

> Uncertainty is reconciled. It is never used as permission to repeat an economic command.