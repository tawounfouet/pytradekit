# IBKR 0.8.0b8 PAPER Compliance Qualification

## Status

LOT-06.7 implements the real PAPER evidence and compliance certification harness.

Standard CI remains provider-free and can certify only deterministic C2 behavior.

No retained real IBKR PAPER evidence is bundled in the current repository state.

Therefore:

~~~text
deterministic IBKR capabilities = C2
retained real PAPER C3 evidence = not yet captured
TRADING_READY = closed
LIVE = unavailable
~~~

## Chain of trust

Official C3 evidence requires:

~~~text
successful CI run on exact commit
-> verified by GitHub Actions API
-> self-hosted IBKR PAPER workflow
-> canonical IBKRExecutionAdapter probe
-> sanitized raw probe report
-> raw provider evidence retained with upload-artifact
-> retained provider artifact_id
-> Actions-only evidence normalizer
-> PAPER workflow_run_id
-> deterministic_ci_run_id
-> qualified commit
-> ib_async 2.1.0
-> masked account identity
-> canonical bundle SHA-256
-> ComplianceHarness replay
-> capability-specific C3 only
~~~

## Integrity

The retained bundle hash is calculated over the canonical JSON representation while excluding only provenance.artifact_json_sha256 itself.

IBKRPaperEvidenceBundle.from_dict() verifies the hash before parsing the retained evidence.

build_ibkr_certification_run() verifies integrity again before any C3 replay.

Any retained payload mutation after capture invalidates the evidence.

## Controlled provider execution

The real PAPER probe routes MARKET, LIMIT, CANCEL and cleanup economic writes through IBKRExecutionAdapter.

The probe script contains no direct placeOrder or cancelOrder call.

All provider outcomes retain the existing LOT-06.5 no-blind-retry semantics.

## Current conservative C3 contract

A successful controlled workflow may promote only capabilities whose exact proof contract passes.

Current normalization deliberately does not claim C3 for:

~~~text
ACCOUNT_QUERY
because explicit account restriction evidence is not captured yet

PARTIAL_FILL
because a real partial fill must actually be observed

EXECUTION_FACTS
because canonical Fill mapping from captured execDetails is not yet replayed by the real probe

RECONNECT_RECOVERY
because the controlled reconnect observation does not yet prove fresh reconciliation plus write readmission
~~~

Those capabilities remain C2 even if the broader controlled probe succeeds.

Other capabilities are promoted only when their required PAPER gates and normalized proof fields pass.

## Local diagnostics

A local controlled PAPER probe may be used for diagnosis.

It is not official C3 evidence.

The C3 normalizer requires:

~~~text
GITHUB_ACTIONS=true
GITHUB_WORKFLOW=IBKR Real PAPER Certification
GITHUB_SHA=<qualified commit>
GITHUB_RUN_ID=<PAPER workflow run>
~~~

and the workflow verifies the supplied deterministic CI run against the GitHub Actions API before the probe.

## Artifacts

The official workflow first retains real-paper-probe.json as provider evidence and injects that artifact_id into the normalized bundle before C3 replay.

It then retains:

~~~text
real-paper-evidence.json
real-paper-certification.json
~~~

The normalized evidence artifact is the certification source of truth.

## Promotion

After a successful real PAPER workflow, freeze the sanitized retained bundle and observed certification matrix before preparing 0.8.0rc1.
