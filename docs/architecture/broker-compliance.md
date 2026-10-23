# Broker Compliance Architecture

PyTradeKit 0.8 defines a provider-neutral compliance layer above broker adapters and below release qualification.

## Purpose

The compliance system proves broker neutrality through shared economic and operational semantics.

The governing rule is:

> Normalize semantics, not provider features.

The compliance core must not import a concrete provider adapter or SDK.

## Package boundary

~~~text
pytradekit.brokers.compliance
|
|-- BrokerCapability
|-- CapabilityConstraint
|-- CapabilitySupport
|-- CertificationLevel
|-- ProviderCapabilityManifest
|-- ContractVersion
|-- BrokerAdapterContract
|-- ProviderFixture
|
|-- ComplianceRequirement
|-- ComplianceScenario
|-- ComplianceResult
|-- ComplianceEvidence
|-- ComplianceReport
|-- CertifiedCapability
|
|-- ComplianceHarness
|-- ComplianceObservation
|-- EvidenceSanitizer
|-- CertificationRegistry
`-- StaleEvidencePolicy
~~~

LOT-01 introduced the contract candidate and manifest. LOT-02 adds executable qualification and retained evidence.

## Existing ProviderManifest

The runtime ProviderManifest introduced in milestone 0.5 remains in place for the frozen Alpaca PAPER runtime.

ProviderCapabilityManifest is the 0.8 compliance declaration. It answers what an adapter claims to support.

Certification answers what retained evidence proves.

LOT-03 maps Alpaca into the new compliance model.

## Capability taxonomy

P0 capabilities:

~~~text
ACCOUNT_QUERY
ORDER_QUERY
MARKET_ORDER
LIMIT_ORDER
CANCEL_ORDER
PARTIAL_FILL
POSITION_QUERY
BALANCE_QUERY
CLIENT_ORDER_REFERENCE
EXECUTION_FACTS
RECONNECT_RECOVERY
~~~

Optional capabilities:

~~~text
LATEST_QUOTE
REPLACE_ORDER
~~~

Capabilities may carry constraints for asset class, order type, time in force, runtime environment, account mode and provider settings.

## Certification levels

~~~text
C0 DEFINED
C1 IMPLEMENTED
C2 INTEGRATION QUALIFIED
C3 PAPER QUALIFIED
C4 LIVE LIMITED
C5 LIVE QUALIFIED
~~~

C3 requirements must require PAPER evidence. C4 and C5 requirements must require LIVE evidence.

PyTradeKit 0.8 remains PAPER-focused and LIVE remains unavailable.

## ComplianceRequirement

A requirement identifies:

~~~text
requirement_id
capability
level
description
criticality
applicable
evidence_type
~~~

Criticality is:

~~~text
CRITICAL
HIGH
MEDIUM
LOW
~~~

A critical semantic failure cannot be converted into C3 by a report waiver.

## ComplianceScenario

A scenario describes:

~~~text
scenario_id
capability
preconditions
action
expected_result
failure_semantics
cleanup
required_evidence
requirement_ids
~~~

The additional requirement_ids field provides the executable link between requirement definitions and scenario results.

Provider-specific executor code remains outside the scenario model.

## ComplianceResult

Statuses are explicit and non-interchangeable:

~~~text
PASS
FAIL
BLOCKED
NOT_APPLICABLE
~~~

BLOCKED is used when qualification cannot validly execute because a precondition or external dependency is unavailable.

FAIL is used when the required behavior executes and the observed result violates the requirement.

The harness does not collapse BLOCKED into FAIL.

## Evidence model

Each ComplianceEvidence record is linked to:

~~~text
evidence_id
scenario_id
provider
environment
commit
adapter version
SDK version
contract version
evidence type
capture time
artifact reference
sanitized payload
~~~

Candidate artifact location:

~~~text
artifacts/qualification/brokers/{provider}/{run_id}.json
~~~

ComplianceRun.to_json produces deterministic JSON-ready qualification output containing the report, retained evidence and generated certification registry.

## Evidence sanitization

EvidenceSanitizer accepts only JSON-like values plus deterministic conversions for datetime, Decimal and Enum.

It redacts:

~~~text
secret-like keys
authorization markers
known sensitive values supplied by the qualification caller
~~~

Raw provider SDK objects are rejected instead of being serialized into compliance evidence.

The complete ComplianceRun artifact is secret-scanned again after report generation.

## ComplianceHarness

ComplianceHarness receives:

~~~text
BrokerAdapterContract
ComplianceRequirement[]
ComplianceScenario[]
scenario executors
EvidenceSanitizer
ComplianceReportGenerator
ClockPort
~~~

The same harness consumes any ProviderFixture.

Provider-specific behavior is injected only through scenario executors and the ProviderFixture implementation.

The harness:

~~~text
validate manifest
-> resolve applicability
-> execute scenario
-> preserve PASS / FAIL / BLOCKED / NOT_APPLICABLE
-> run cleanup
-> sanitize evidence
-> retain evidence references
-> calculate capability certification
-> generate report
-> generate static registry
-> secret-scan complete artifact
~~~

Cleanup failure changes the scenario result to BLOCKED because qualification baseline restoration is no longer trustworthy.

## Certification calculation

A declared capability starts at C0.

It moves upward only when all applicable requirements through a target level have passing scenario results with the exact required evidence type.

C3 additionally requires a PAPER environment and PAPER evidence.

C4 and C5 are not issued by the current PAPER-only runtime.

## CertificationRegistry

CertificationRegistry is an immutable generated registry for 0.8.

Each CertifiedCapability records:

~~~text
provider
environment
capability
certification level
constraints
contract version
qualified commit
adapter version
SDK version
qualified_at
evidence refs
known limitations
~~~

The registry is not provider health, authorization, safety or risk state.

~~~text
certified capability
!= currently healthy provider

provider supports
!= actor authorized

provider supports
!= action safe now

provider supports
!= risk allowed
~~~

## StaleEvidencePolicy

Certification evidence is invalidated when material runtime identity changes.

The policy checks:

~~~text
provider
environment
adapter version
SDK name/version
contract version
optional exact commit
optional maximum evidence age
~~~

CertificationRegistry.find_current returns no certification when any retained evidence reference is missing or stale.

This prevents old evidence from being displayed as current after an adapter or SDK change.

## Fitness functions

LOT-01 provides FF-048 through FF-056.

LOT-02 adds:

~~~text
FF-057 C3 requires PAPER evidence
FF-058 stale evidence cannot certify a changed adapter
FF-059 compliance artifacts must pass secret scan
~~~

FF-060 economic-write retry semantics remains a cross-provider qualification concern and will be exercised when concrete provider suites are connected in LOT-03 and LOT-06.

## Version policy

~~~text
0.8       BrokerAdapterContract v1 candidate
0.9       compatibility freeze
1.0       stable BrokerAdapterContract v1
~~~

The current contract candidate is 1.0-rc1.

The ProviderCapabilityManifest schema candidate is also identified as 1.0-rc1.

## Explicit non-goals of LOT-02

LOT-02 does not implement:

- Alpaca compliance mapping;
- Alpaca CertifiedCapability records from real PAPER evidence;
- IBKR SDK or session handling;
- IBKR mappings;
- IBKR execution;
- provider-specific reconciliation;
- LIVE qualification.

Those concerns belong to later 0.8 LOTs.
