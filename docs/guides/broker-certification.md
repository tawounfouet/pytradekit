# Broker Certification Guide

This guide describes the PyTradeKit 0.8 compliance workflow introduced by LOT-02.

## Core distinction

ProviderCapabilityManifest declares support.

CertifiedCapability records qualification backed by retained evidence.

Do not treat a manifest capability as certified merely because an adapter exposes it.

## Build the requirement suite

Each ComplianceRequirement defines:

~~~text
capability
target certification level
criticality
applicability
required evidence type
~~~

C3 requirements must use PAPER evidence.

C4 and C5 requirements must use LIVE evidence.

## Define scenarios

ComplianceScenario describes provider-neutral behavior.

A scenario links to one or more requirement IDs and declares:

~~~text
preconditions
action
expected result
failure semantics
cleanup
accepted evidence types
~~~

Do not place SDK objects or provider-specific enums in the scenario model.

## Provide executors

The common harness does not know Alpaca or IBKR.

Provider-specific scenario execution is supplied through ComplianceScenarioExecutor.

An executor returns ComplianceObservation with:

~~~text
status
evidence type
sanitizable payload
optional reason
~~~

Expected status semantics:

~~~text
PASS            required behavior proved
FAIL            behavior executed but violated the requirement
BLOCKED         valid qualification could not execute
NOT_APPLICABLE  scenario requirement does not apply
~~~

Use ComplianceBlockedError only for declared blocked conditions.

Use ComplianceScenarioFailure when the behavior executed and violated the requirement.

Unexpected exceptions are recorded by type only, without retaining exception messages that could contain credentials.

## Cleanup

ProviderFixture.cleanup runs after each executed scenario.

A cleanup exception makes the scenario BLOCKED.

Do not promote a run while the provider baseline is uncertain.

## Evidence safety

Pass known secret values to ComplianceHarness.run through sensitive_values when they may occur in provider diagnostics.

EvidenceSanitizer also redacts common secret-like keys and authorization markers.

Raw SDK objects are rejected.

The final ComplianceRun artifact is scanned after report and registry generation.

## Run the harness

Conceptually:

~~~python
run = harness.run(
    fixture,
    run_id="provider-paper-qualification",
    commit_sha="qualified-commit",
    manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    sensitive_values=(resolved_api_key, resolved_secret),
)
~~~

The result contains:

~~~text
run.report
run.evidence
run.registry
run.to_json()
~~~

## Certification levels

A capability begins at C0 when declared.

The harness promotes it only when the applicable requirement suite passes with the correct evidence class.

For C3:

~~~text
PAPER environment
+
PAPER evidence
+
all required scenarios PASS
+
cleanup trustworthy
+
retained sanitized evidence
~~~

are required.

## Stale evidence

Use StaleEvidencePolicy before consuming a generated registry as current qualification.

Evidence becomes stale or mismatched when the provider, environment, adapter version, SDK version or contract version differs.

An optional maximum age and exact commit policy can make the check stricter.

CertificationRegistry.find_current returns None when evidence is absent or stale.

## Health, authorization, safety and risk

Certification is only one gate.

The execution chain remains:

~~~text
Capability Supported?
-> Capability Qualified Enough?
-> Authorized?
-> Safe?
-> Risk Allowed?
-> Runtime Ready?
-> ExecutionPort
-> Provider Adapter
~~~

A C3 capability does not imply that the provider is currently healthy or that a specific action is currently authorized or safe.

## Current milestone

0.8.0a2 provides the common test kit and evidence model.

LOT-03 will connect the existing Alpaca PAPER integration to this harness and produce provider-specific CertifiedCapability evidence.
