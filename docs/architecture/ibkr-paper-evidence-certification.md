# IBKR PAPER Evidence and Compliance Certification

## Architecture

~~~text
IBKR deterministic adapter gates
-> C2

successful deterministic CI on exact commit
-> manual real PAPER controlled probe through IBKRExecutionAdapter
-> raw provider evidence retained by GitHub Actions
-> retained provider artifact_id
-> Actions-only evidence normalization
-> canonical bundle SHA-256 verification
-> sanitized retained bundle
-> ComplianceHarness replay
-> capability-specific C3
~~~

## No evidence, no C3

The certification baseline is C2 for every declared IBKR capability.

No static list of pre-certified C3 capabilities exists.

## Evidence identity

Each retained bundle is bound to provider, PAPER environment, qualified commit, ib_async version, canonical artifact SHA-256, masked account, retained provider artifact ID, PAPER workflow run ID and deterministic CI run ID.

The canonical hash excludes only its own self-referential hash field. Parsing or certification rejects a bundle whose content no longer matches that hash.

## Capability isolation

C3 promotion is capability-specific. One successful MARKET order does not certify PARTIAL_FILL or RECONNECT_RECOVERY.

## Real provider workflow

The real PAPER workflow is manual and self-hosted because IB Gateway is loopback-bound by the qualified runtime.

Standard CI never creates PAPER orders. The C3 normalizer runs only inside the IBKR Real PAPER Certification GitHub Actions workflow and verifies its GITHUB_SHA and GITHUB_RUN_ID.

## Safety

Every controlled MARKET, LIMIT, CANCEL and cleanup write flows through IBKRExecutionAdapter. The evidence script contains no direct placeOrder or cancelOrder call.

No LIVE endpoint exists.

Cleanup is evidence, not an assumption. Its correction quantity is derived from provider fills observed for the probe, and an interrupted scenario may attempt cleanup only once before shutdown.

TRADING_READY remains closed until retained real PAPER certification is available.
