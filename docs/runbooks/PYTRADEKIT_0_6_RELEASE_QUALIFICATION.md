# PyTradeKit 0.6 - Release Qualification

## Objective

LOT-08 proves that reconciliation either converges safely or remains safely blocked under uncertainty and failure.

## Required deterministic gates

~~~text
typography
ruff
strict mypy
import architecture
architecture/public imports
production fault qualification
unit/property/integration/E2E/qualification tests
release artifact qualification
~~~

## P0 scenario matrix

The release gate covers:

1. clean startup -> CONSISTENT/HIGH
2. missing Fill -> import once -> verify -> convergence
3. external manual activity -> explicit unknown origin -> blocked review
4. uncertain submit -> read-side proof -> no second submit
5. reconnect -> containment -> fresh reconciliation
6. missed stream Fill -> periodic recovery -> one effect
7. stale correction -> no side effect -> fresh run
8. partial snapshot -> no HIGH confidence
9. durable-state outage -> fail closed -> fresh recovery
10. critical position divergence -> CRITICAL and blocked
11. duplicate imported Fill -> one economic effect
12. process kill during reconciliation -> stale run closed -> no duplicate repair
13. Outbox/commit failure -> atomic rollback -> safe replay

Existing 0.5 fault qualification remains active for Inbox/Outbox crash windows, duplicate provider events, and post-commit replay.

## Release candidate rule

0.6.0rc2 may be published only after all deterministic gates pass on the exact release metadata commit.

## Stable promotion rule

0.6.0 may be published only after:

- 0.6.0rc2 CI passes
- the rc2 package artifacts pass clean-install qualification
- the GitHub rc2 pre-release contains wheel, sdist and SHA256SUMS
- no release blocker remains from the scenario matrix
- stable metadata is requalified on its own commit

## Stable release meaning

0.6.0 Qualified Release means:

~~~text
detect
-> classify
-> resolve when proven safe
-> verify from fresh evidence
-> prove convergence
-> resume only when consistency and confidence allow it
~~~


## Final rc2 qualification evidence

The corrected rc2 source candidate was qualified on:

~~~text
commit                       422f92f2ee88d004ce6317153ad49c1013a45f80
CI run                       39818837375
PostgreSQL                   16
full test suite              455 passed
architecture/public imports  PASS
production fault suite       PASS
release artifact qualifier   PASS
~~~

The release workflow was then hardened so a new version cannot be published until the same complete quality gate succeeds inside the publication job itself.
