# Deployment Hardening Architecture

PyTradeKit 0.7.0rc1 defines a production-like single-node PAPER deployment profile. LIVE is not implemented and cannot be selected.

Runtime configuration stores only SecretRef values using env://, file://, or external:// schemes. Secret values are resolved only at infrastructure boundaries.

Production-like PostgreSQL expectations are TLS required, bounded connect timeout, bounded statement timeout, bounded pool size, migration before runtime, and credentials referenced through SecretRef.

Only the qualified Alpaca PAPER endpoints are accepted. Configuration cannot redirect the 0.7 runtime to the Alpaca LIVE trading endpoint.

ProductionRuntimeSupervisor supports bounded startup. A timeout leaves RuntimeAdmissionGate DEGRADED. Late startup completion cannot reopen admission because only the supervisor applies readiness to the gate.

Shutdown keeps its bounded economic drain and adds a separate bounded telemetry flush. Telemetry flush failure is observable but cannot prevent STOPPED state.

The container exposes only GET /health/live and GET /health/ready. It runs unprivileged, read-only, with Linux capabilities dropped and no-new-privileges enabled.

The container entrypoint runs Alembic migrations before starting the runtime health service. Alembic resolves its database URL through the same SecretRef model and alembic.ini persists no database URL.
