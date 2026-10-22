# 47 - PyTradeKit - LOT-05 PAPER Runtime Configuration

**Projet :** PyTradeKit  
**Milestone :** `0.5.x - Persistence + Alpaca Paper`  
**Lot :** `LOT-05 - PAPER Runtime Configuration`  
**Date :** 2026-10-22  
**Statut :** Implementation  
**Contrat provider :** `46_PYTRADEKIT_ALPACA_INTEGRATION_CONTRACT_FREEZE.md`

---

## 1. Objectif

LOT-05 transforme le contrat Alpaca gele en un bootstrap runtime executable.

Le lot introduit :

```text
RuntimeProfile
SecretsPort
EnvironmentSecrets
PAPER hard lock
ProviderManifest
Alpaca composition root
startup readiness
sanitized readiness CLI
```

Le lot ne construit pas encore le runtime complet de trading.

En particulier :

```text
trade_updates production consumer
startup reconciliation service
strategy admission
order execution application wiring
full trading readiness
```

restent dans les lots suivants.

---

## 2. Architecture

```text
Environment configuration
        |
        v
RuntimeProfile
        |
        +----------------------+
        |                      |
        v                      v
SecretsPort              ProviderManifest
        |                      |
        v                      |
EnvironmentSecrets             |
        |                      |
        +----------+-----------+
                   |
                   v
       Alpaca PAPER Composition Root
                   |
       +-----------+-----------+----------------+
       |                       |                |
       v                       v                v
TradingClient            Command Client   Market Data Client
paper=True               paper=True       Stock Historical
                         retry=0
       |
       v
Startup Readiness
       |
       +-- PostgreSQL
       +-- expected account identity
       +-- account blocked state
       +-- trading blocked state
       +-- market clock
```

---

## 3. RuntimeProfile

Le profile est construit a partir de configuration non secrete.

Variables :

```text
PYTRADEKIT_RUNTIME_ENVIRONMENT=PAPER
PYTRADEKIT_RUNTIME_PROFILE=alpaca-paper
PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID=<expected account>
PYTRADEKIT_ALPACA_DATA_FEED=iex
```

Le profile ne contient jamais les valeurs de secrets.

Il contient des references :

```text
env://PYTRADEKIT_ALPACA_PAPER_API_KEY
env://PYTRADEKIT_ALPACA_PAPER_SECRET_KEY
env://PYTRADEKIT_DATABASE_URL
```

---

## 4. Hard lock PAPER

L'enum runtime 0.5 contient uniquement :

```text
PAPER
```

Un environnement :

```text
LIVE
```

est invalide a la construction.

Le composition root verifie a nouveau :

```text
provider == alpaca
environment == PAPER
feed == iex
```

Le lock est donc applique a deux niveaux :

```text
configuration boundary
+
provider composition boundary
```

---

## 5. SecretsPort

Contrat :

```text
resolve(SecretRef) -> secret value
```

Le RuntimeProfile ne sait pas ou le secret est stocke.

LOT-05 fournit un adapter :

```text
EnvironmentSecrets
```

supportant :

```text
env://...
```

Un futur adapter peut fournir :

```text
Vault
AWS Secrets Manager
Azure Key Vault
```

sans changer le RuntimeProfile.

---

## 6. Database URL as secret

La connection string PostgreSQL peut contenir :

```text
username
password
host
```

Elle est donc elle aussi resolue via SecretsPort.

Variable locale :

```text
PYTRADEKIT_DATABASE_URL
```

---

## 7. ProviderManifest

Le manifest 0.5 expose :

```text
provider = alpaca
environment = PAPER
sdk = alpaca-py==0.44.0
asset_scope = US_EQUITY
order_types = MARKET,LIMIT
time_in_force = DAY
market_data_feed = iex
```

Capabilities :

```text
ACCOUNT_QUERY
ASSET_QUERY
CANCEL
LATEST_QUOTE
MARKET_ORDER
LIMIT_ORDER
ORDER_QUERY
POSITION_QUERY
TRADE_UPDATES
```

Le manifest ne contient aucun secret ni account ID.

---

## 8. Composition root

Entry point :

```python
build_alpaca_paper_runtime(profile, secrets)
```

Il construit :

```text
PostgreSQL Engine
Session factory
TradingClient read-side
AlpacaPaperCommandClient
StockHistoricalDataClient
ProviderManifest
AlpacaPaperStartupReadiness
```

---

## 9. Command transport safety

Le command client est :

```text
PAPER
```

et force :

```text
SDK retry count = 0
```

Cela preserve le freeze 46 :

```text
one economic command
=> at most one provider submit attempt
```

Le lot ne soumet encore aucun ordre.

---

## 10. Read-side client

Le read-side client utilise :

```text
TradingClient(..., paper=True)
```

Il sera utilise pour les queries et startup checks.

---

## 11. Startup readiness

LOT-05 introduit :

```text
StartupReadinessReport
```

Il ne doit pas etre confondu avec :

```text
TRADING_READY
```

---

## 12. States

```text
READY_FOR_STARTUP
NOT_READY
```

Le report ajoute explicitement :

```text
trading_ready = false
```

tant que stream et reconciliation ne sont pas wires.

---

## 13. Readiness checks

Le startup report verifie :

```text
profile
provider manifest
PostgreSQL connectivity
provider account identity
account_blocked
trading_blocked
market clock
```

---

## 14. Account safety

Le compte retourne par Alpaca doit correspondre exactement a :

```text
PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID
```

Le report n'affiche jamais l'identite complete.

---

## 15. Account blocked state

Le runtime refuse la readiness si Alpaca indique :

```text
account_blocked
```

ou :

```text
trading_blocked
```

---

## 16. PostgreSQL readiness

Le check utilise :

```text
SELECT 1
```

via l'infrastructure persistence existante.

---

## 17. Market clock

Le startup valide qu'un clock provider est accessible.

Le marche n'a pas besoin d'etre ouvert pour :

```text
READY_FOR_STARTUP
```

car startup readiness n'est pas une admission d'ordre.

---

## 18. Secret-safe diagnostics

Les sorties ne contiennent pas :

```text
API key
API secret
database URL
database password
full provider account ID
```

---

## 19. Readiness CLI

Commande :

```bash
python scripts/alpaca_paper_runtime_readiness.py
```

---

## 20. Required environment

```bash
export PYTRADEKIT_RUNTIME_ENVIRONMENT="PAPER"
export PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID="..."
export PYTRADEKIT_ALPACA_PAPER_API_KEY="..."
export PYTRADEKIT_ALPACA_PAPER_SECRET_KEY="..."
export PYTRADEKIT_DATABASE_URL="postgresql+psycopg://..."
```

Feed optional :

```bash
export PYTRADEKIT_ALPACA_DATA_FEED="iex"
```

---

## 21. Sanitized report

Exemple structurel :

```json
{
  "profile": {
    "provider": "alpaca",
    "environment": "PAPER",
    "account": "********1234",
    "market_data_feed": "iex"
  },
  "manifest": {},
  "readiness": {
    "state": "READY_FOR_STARTUP",
    "ready_for_startup": true,
    "trading_ready": false,
    "checks": []
  }
}
```

---

## 22. Exit codes

```text
0
READY_FOR_STARTUP

1
infrastructure/provider readiness failure

2
configuration/secret resolution failure
```

---

## 23. Tests

Unit tests couvrent :

```text
PAPER profile
LIVE rejection
explicit environment requirement
expected account requirement
IEX lock
safe repr
secret resolution
missing secrets
unsupported secret scheme
readiness aggregation
account identity mismatch
blocked account
database unhealthy
composition root
command retry=0
```

---

## 24. Architecture tests

Ils verifient :

```text
no LIVE endpoint
no LIVE enum member
paper=True
command retries=0
readiness CLI has no trading commands
runtime composition resolves secrets only through SecretsPort
```

---

## 25. LOT-05 output

A la fin du lot :

```text
configuration contract
        YES

secret boundary
        YES

PAPER hard lock
        YES

provider manifest
        YES

composition root
        YES

startup readiness
        YES

trading readiness
        NO - later lot

real provider startup evidence
        requires local credentials
```

---

## 26. Next implementation

Le prochain lot peut maintenant construire :

```text
Alpaca execution adapter
```

sur cette composition, avec :

```text
ExecutionPort
safe submit
safe cancel
query_order
canonical mappings
```

puis le private event consumer et reconciliation.

---

## 27. Final principle

> Runtime configuration may select safe infrastructure, but it must never silently widen the economic capability envelope.