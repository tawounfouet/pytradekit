# IBKR 0.8 Compliance Certification

## Deterministic baseline

0.8.0b8 qualifies the certification machinery but intentionally bundles no real IBKR PAPER evidence.

Therefore deterministic CI must produce:

~~~text
all declared capabilities <= C2
C3 claims = 0
~~~

## Real PAPER promotion

C3 requires a retained IBKRPaperEvidenceBundle generated from a real provider probe.

The bundle includes commit provenance and the SHA-256 of the sanitized probe report.

## C3 eligible capabilities

~~~text
ACCOUNT_QUERY
ORDER_QUERY
MARKET_ORDER
LIMIT_ORDER
CANCEL_ORDER
POSITION_QUERY
BALANCE_QUERY
CLIENT_ORDER_REFERENCE
EXECUTION_FACTS
RECONNECT_RECOVERY
~~~

PARTIAL_FILL remains C2 until directly observed.

## Current 0.8.0b8 state

~~~text
real_provider_used = false in CI
retained_paper_evidence_present = false
C3 claimed = false
LIVE available = false
~~~
