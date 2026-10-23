# IBKR PAPER Evidence and Compliance Certification

## Architecture

~~~text
IBKR deterministic adapter gates
-> C2

manual real PAPER controlled probe
-> sanitized retained bundle
-> ComplianceHarness replay
-> capability-specific C3
~~~

## No evidence, no C3

The certification baseline is C2 for every declared IBKR capability.

No static list of pre-certified C3 capabilities exists.

## Evidence identity

Each retained bundle is bound to provider, PAPER environment, qualified commit, ib_async version, artifact SHA-256 and masked account.

## Capability isolation

C3 promotion is capability-specific. One successful MARKET order does not certify PARTIAL_FILL or RECONNECT_RECOVERY.

## Real provider workflow

The real PAPER workflow is manual and self-hosted because IB Gateway is loopback-bound by the qualified runtime.

Standard CI never creates PAPER orders.

## Safety

Every controlled write uses one provider call site.

No LIVE endpoint exists.

Cleanup is evidence, not an assumption.

TRADING_READY remains closed until retained real PAPER certification is available.
