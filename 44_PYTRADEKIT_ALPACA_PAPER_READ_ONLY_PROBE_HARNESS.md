# 44 - PyTradeKit - Alpaca PAPER Read-Only Probe Harness

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-04E - Alpaca PAPER Read-Only Probes`  
**Date :** 2026-10-22  
**Statut :** Implemented harness - real PAPER execution requires user credentials  
**SDK qualifie :** `alpaca-py==0.44.0`

---

## 1. Objectif

Ce lot introduit le premier contact executable entre PyTradeKit et un vrai environnement Alpaca PAPER.

Il est volontairement :

```text
READ-ONLY
PAPER-ONLY
OPT-IN
NO LIVE FALLBACK
NO ORDER SUBMISSION
NO CANCEL
NO POSITION CLOSE
NO DATABASE MUTATION
```

Le but n'est pas encore de construire l'adapter Alpaca final.

Le but est de produire des preuves provider reelles sur :

```text
authentication
account identity
market clock
asset metadata
positions
open orders
latest quote
trade_updates connectivity
```

avant LOT-04F, qui couvrira les ordres controles en PAPER.

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
THIS LOT

45 - Alpaca Controlled PAPER Order Probe
NEXT

46 - Alpaca Integration Contract Freeze
LATER

LOT-05 - PAPER Runtime Configuration
LATER
```

---

## 3. Principes de securite

Le probe ne contient aucun chemin fonctionnel vers :

```text
submit_order
replace_order_by_id
cancel_orders
cancel_order_by_id
close_all_positions
close_position
exercise_options_position
```

Une architecture test verifie explicitement cette propriete.

Le builder Alpaca utilise :

```python
TradingClient(..., paper=True)
TradingStream(..., paper=True)
```

Il n'existe aucun argument `live`, aucun choix d'endpoint LIVE et aucun fallback LIVE dans le harness.

---

## 4. Dependence optionnelle

Le SDK n'entre pas dans les dependances de base de PyTradeKit.

Il est ajoute comme extra :

```toml
[project.optional-dependencies]
alpaca = [
  "alpaca-py==0.44.0",
]
```

Installation :

```bash
python -m pip install -e ".[alpaca]"
```

Pour developpement complet :

```bash
python -m pip install -e ".[dev,postgres,alpaca]"
```

---

## 5. Variables d'environnement

Les secrets ne sont jamais passes en arguments CLI afin d'eviter leur presence dans l'historique shell.

Variables obligatoires :

```text
PYTRADEKIT_ALPACA_PAPER_API_KEY
PYTRADEKIT_ALPACA_PAPER_SECRET_KEY
```

Variables optionnelles :

```text
PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID
PYTRADEKIT_ALPACA_PROBE_SYMBOL
PYTRADEKIT_ALPACA_DATA_FEED
PYTRADEKIT_ALPACA_STREAM_SECONDS
```

Defaults :

```text
symbol = AAPL
feed = iex
stream_seconds = 5
```

---

## 6. Pourquoi `expected_account_id`

Le probe peut fonctionner sans cette valeur parce qu'il est read-only.

Mais il est fortement recommande de definir :

```text
PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID
```

Le probe compare alors l'ID retourne par Alpaca avec l'ID attendu.

En cas de mismatch :

```text
FAIL CLOSED
```

Le rapport ne publie pas l'ID complet.

---

## 7. Sequence du probe

```text
load config from environment
        |
        v
build TradingClient(paper=True)
        |
        v
build StockHistoricalDataClient
        |
        v
build TradingStream(paper=True)
        |
        v
GET account
        |
        v
verify expected account ID
        |
        v
GET clock
        |
        v
GET asset metadata
        |
        v
GET positions
        |
        v
GET open orders
        |
        v
GET latest quote
        |
        v
listen trade_updates for bounded window
        |
        v
emit sanitized JSON report
```

---

## 8. Endpoints et comportements observes

Le harness utilise uniquement des operations de lecture :

```text
get_account
get_clock
get_asset
get_all_positions
get_orders OPEN
get_stock_latest_quote
trade_updates listener
```

Aucune operation economique n'est exposee.

---

## 9. Market data feed

Default :

```text
IEX
```

Raison :

```text
lowest-friction equity feed for the first read-only qualification
```

Le feed peut etre change par :

```text
PYTRADEKIT_ALPACA_DATA_FEED
```

Les valeurs sont validees contre `alpaca.data.enums.DataFeed`.

---

## 10. Latest quote

Le probe utilise :

```text
StockHistoricalDataClient
+
StockLatestQuoteRequest
```

Il capture notamment :

```text
symbol
feed
timestamp
bid price
bid size
bid exchange
ask price
ask size
ask exchange
```

Les valeurs numeriques sont serialisees en texte dans le rapport de discovery afin de ne pas creer de faux precedent `float` dans le modele canonique.

---

## 11. Account report

Le rapport expose uniquement des informations diagnostiques selectionnees :

```text
masked account ID
masked account number
status
currency
cash
equity
buying power
trading blocked
account blocked
```

Il ne contient pas :

```text
API key
secret key
raw auth headers
full account ID
full account number
```

---

## 12. Masking

Exemple :

```text
11111111-1111-1111-1111-111111111111
```

devient :

```text
***1111
```

Le masking n'est pas une methode de chiffrement.

Il sert uniquement a eviter de publier inutilement l'identite complete du compte dans un rapport de probe.

---

## 13. Positions

Le probe capture en read-only :

```text
asset ID
symbol
asset class
exchange
side
quantity
available quantity
average entry price
market value
current price
```

Il n'ecrit rien dans le Portfolio PyTradeKit.

Le but est uniquement de connaitre la forme provider reelle.

---

## 14. Open orders

La requete est explicitement limitee aux ordres ouverts :

```python
GetOrdersRequest(
    status=QueryOrderStatus.OPEN,
    limit=100,
)
```

Le probe capture :

```text
provider order ID
client_order_id
symbol
status
type
side
TIF
quantity
filled quantity
limit price
stop price
submitted_at
```

Cette observation alimentera LOT-04F et la reconciliation.

---

## 15. trade_updates

Le harness peut ouvrir un :

```text
TradingStream(paper=True)
```

et s'abonner uniquement a :

```text
trade_updates
```

pendant une fenetre bornee.

Default :

```text
5 seconds
```

---

## 16. Absence d'event

Aucun ordre n'est cree par ce lot.

Il est donc parfaitement normal que :

```text
trade_updates count = 0
```

pendant la fenetre.

Le rapport emet un warning informatif, pas un failure.

---

## 17. Pourquoi observer trade_updates des maintenant

Cela permet deja de qualifier :

```text
stream construction
authentication path
subscription path
bounded lifecycle
shutdown path
```

sans introduire d'effet economique.

Le contenu des vrais events sera qualifie plus profondement en LOT-04F lors des ordres controles.

---

## 18. Stream stop

Le probe demarre le SDK stream dans un worker thread daemon.

Apres la fenetre configuree :

```text
stream.stop()
```

est demande puis le worker est joint avec un timeout borne.

Le report contient :

```text
status
duration_seconds
event_count
```

---

## 19. Limitation du stream probe

`alpaca-py` gere lui-meme les erreurs/reconnections dans `TradingStream.run()`.

Par consequent, un event count nul ne permet pas de conclure a lui seul :

```text
stream authentication failed
```

ou :

```text
stream authenticated but no account event occurred
```

LOT-04F ajoutera des events provoques en PAPER et permettra une preuve plus forte.

---

## 20. Lancement

Exemple macOS/Linux :

```bash
export PYTRADEKIT_ALPACA_PAPER_API_KEY="..."
export PYTRADEKIT_ALPACA_PAPER_SECRET_KEY="..."
export PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID="..."
export PYTRADEKIT_ALPACA_PROBE_SYMBOL="AAPL"
export PYTRADEKIT_ALPACA_DATA_FEED="iex"
export PYTRADEKIT_ALPACA_STREAM_SECONDS="5"

python scripts/alpaca_paper_probe.py
```

---

## 21. Rapport fichier

Pour conserver le rapport sanitise :

```bash
python scripts/alpaca_paper_probe.py \
  --output artifacts/alpaca/paper-read-only-probe.json
```

Le dossier parent est cree automatiquement.

---

## 22. Exemple de rapport

Structure :

```json
{
  "environment": "PAPER",
  "sdk_version_target": "alpaca-py==0.44.0",
  "account": {
    "id": "***1111",
    "account_number": "***6789"
  },
  "clock": {},
  "asset": {},
  "positions": [],
  "open_orders": [],
  "latest_quote": {},
  "trade_updates": [],
  "stream": {
    "status": "window_completed",
    "duration_seconds": 5.0,
    "event_count": 0
  },
  "warnings": []
}
```

---

## 23. CI policy

La CI installe l'extra :

```text
alpaca
```

pour :

```text
import checking
mypy
unit tests
architecture tests
```

Mais elle ne fournit aucun credential PAPER.

Elle n'execute donc jamais de requete reseau Alpaca.

---

## 24. Unit tests

Les tests utilisent des fakes locaux pour verifier :

```text
credential validation
secret-safe repr
symbol normalization
feed parsing
account mismatch fail-closed
sanitized report
bounded stream observation
PAPER forced in client builder
```

---

## 25. Architecture tests

Deux garanties sont testees par AST/source inspection :

```text
no provider write method invocation
no LIVE endpoint reference
```

Le test exige egalement :

```text
paper=True
```

pour le trading client et le private trading stream.

---

## 26. Why this is not the production adapter

Le harness ne fournit pas encore :

```text
canonical mappings
ProviderOrderIdentity
ProviderAccountIdentity
ProviderInstrumentMapping
Inbox processing
Outbox integration
PostgreSQL snapshots
reconciliation workflow
retry policy wrapper
safe submit transport
observability production
```

Il ne doit donc pas etre utilise comme adapter runtime 0.5 final.

---

## 27. Read retry policy

Le SDK `TradingClient` conserve ici son comportement read-side actuel.

Cela est acceptable parce que les calls exposes sont :

```text
GET / read operations
```

La future commande `submit_order` ne reutilisera pas implicitement cette policy.

---

## 28. Critical distinction

```text
read retry
!=
economic command retry
```

LOT-04F devra prouver :

```text
one PyTradeKit submit
=> at most one transport submission attempt
```

avant de valider l'adapter d'execution.

---

## 29. Probe output is discovery evidence

Le JSON genere doit etre considere comme :

```text
provider discovery evidence
```

pas comme :

```text
canonical database state
```

---

## 30. Fixture promotion

Apres execution reelle et inspection :

```text
sanitized provider observations
```

pourront etre transformees en fixtures sous :

```text
tests/fixtures/alpaca/
```

---

## 31. No fixture before observation

Ne pas inventer de fixtures provider pretendument reelles avant d'avoir execute le probe contre PAPER.

---

## 32. Gate LOT-04E

Le lot est considere code-complete si :

```text
[ ] optional alpaca dependency exists
[ ] PAPER-only builder exists
[ ] no LIVE selector exists
[ ] credentials come from environment/secrets boundary
[ ] account read works structurally
[ ] clock read works structurally
[ ] asset read works structurally
[ ] positions read works structurally
[ ] open orders read works structurally
[ ] latest quote read works structurally
[ ] trade_updates observation is bounded
[ ] output is sanitized
[ ] write methods are absent
[ ] unit tests cover safety invariants
[ ] architecture tests cover read-only boundary
[ ] CI never contacts Alpaca
```

---

## 33. Runtime verification gate

Le lot n'est pas provider-qualified tant qu'un vrai run PAPER n'a pas confirme :

```text
[ ] PAPER authentication succeeds
[ ] expected account matches
[ ] account snapshot received
[ ] market clock received
[ ] AAPL or configured asset metadata received
[ ] positions list received
[ ] open orders list received
[ ] latest quote received
[ ] trade stream starts and stops cleanly
[ ] no secret appears in report
```

---

## 34. No credentials in repository

Aucun credential PAPER ne doit etre commite.

Le `.env` personnel doit rester hors repository.

---

## 35. Recommended local workflow

```text
install alpaca extra
        |
        v
export PAPER credentials
        |
        v
set expected account ID
        |
        v
run read-only probe
        |
        v
inspect sanitized JSON
        |
        v
sanitize any useful provider examples
        |
        v
capture fixtures
        |
        v
proceed to controlled order probe
```

---

## 36. LOT-04F preview

Le prochain lot pourra alors introduire, toujours en PAPER :

```text
MARKET tiny order
LIMIT away from market
CANCEL
client_order_id
trade_updates capture
partial fill observation when available
uncertain submission experiment
recovery by client_order_id
```

avec une policy de commande differente du SDK read path.

---

## 37. Final decision

Le harness 44 constitue la premiere preuve executable de l'integration Alpaca sans prendre de risque economique.

Il confirme la sequence de delivery :

```text
understand provider
        |
        v
probe reads
        |
        v
capture facts
        |
        v
probe controlled writes
        |
        v
freeze integration contract
        |
        v
build production runtime
```

Le prochain mouvement logique apres un run PAPER read-only reussi est :

```text
45_PYTRADEKIT_ALPACA_CONTROLLED_PAPER_ORDER_PROBE.md
```