# PyTradeKit 0.7 Release Qualification Runbook

## Preconditions

- PostgreSQL test service healthy;
- Python 3.12 environment;
- development, postgres and alpaca extras installed;
- no LIVE configuration available.

## Required gates

Run typography, Ruff, mypy strict, Import Linter, architecture/contracts, production fault qualification, LOT-08 production qualification, the full pytest suite, single-node deployment qualification and release artifact qualification.

## Release blockers

Any unauthorized provider call, safety bypass, KillSwitch bypass, stale governance overwrite, secret leakage, critical health admission leak, state-less critical alert, telemetry corruption of economic state or LIVE activation blocks release.

## Expected release

LOT-08 release candidate is 0.7.0rc2.

LIVE remains unavailable.
