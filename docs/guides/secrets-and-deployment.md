# Secrets and Deployment Guide

Keep sensitive values outside configuration. Use references such as env://PYTRADEKIT_ALPACA_PAPER_API_KEY, file:///run/secrets/alpaca_api_key, or external://trading/alpaca/api-key.

RuntimeProfile accepts references through PYTRADEKIT_ALPACA_API_KEY_REF, PYTRADEKIT_ALPACA_SECRET_KEY_REF, and PYTRADEKIT_DATABASE_URL_REF.

File-backed container values are mounted below /run/secrets. The repository ignores .secrets/.

ExternalSecretsProvider accepts an injected lookup callable so cloud-specific provider SDKs remain outside the core.

RuntimeSecurityConfig.production_like() requires PostgreSQL TLS. The local Docker Compose profile explicitly disables TLS only for its local PostgreSQL container.

Operational commands are pytradekit liveness, pytradekit health, and pytradekit serve-health. Health/readiness checks never claim TRADING_READY.

Credential rotation in 0.7 is restart-based: rotate, restart, resolve, migrate, recompute readiness, reconcile, then restore admission only from fresh safety evidence.
