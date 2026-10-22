# Broker Compliance Architecture

PyTradeKit 0.8 LOT-01 introduces the Broker Adapter Contract Candidate.

## Purpose

The contract exists to prove broker neutrality through shared economic and operational semantics. It does not attempt to make provider SDKs look identical.

The governing rule is:

> Normalize semantics, not provider features.

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
~~~

The compliance package may depend on canonical PyTradeKit types and ports. It must not import a concrete provider adapter.

## Existing ProviderManifest

The runtime ProviderManifest introduced in milestone 0.5 remains in place for the frozen Alpaca PAPER runtime.

LOT-01 does not silently replace it.

ProviderCapabilityManifest is the new 0.8 compliance declaration. LOT-03 will map the existing Alpaca runtime contract into this model and qualify it using the common compliance system.

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

Capabilities may carry constraints for asset class, order type, time in force, runtime environment, account mode and required provider settings.

## Manifest and certification

A ProviderCapabilityManifest answers:

~~~text
what the adapter claims
~~~

Certification answers:

~~~text
what retained evidence proves
~~~

LOT-01 implements the declaration model only. ComplianceRequirement, ComplianceScenario, ComplianceEvidence, ComplianceReport and CertifiedCapability belong to LOT-02.

## Contract dimensions

BrokerAdapterContract v1 candidate covers:

~~~text
identity
capabilities
execution
query
cancellation
facts/events
snapshots
errors
uncertainty
reconnect
reconciliation
readiness
security
safety
health
evidence
~~~

## Core invariants

The candidate mechanically records these cross-provider rules:

~~~text
normalize semantics, not provider features
canonical IDs remain local
provider IDs remain external evidence
no blind retry of economic writes
uncertain outcomes require reconciliation
cancel acknowledgement is not a terminal cancellation fact
execution facts require stable identity
reconnect requires reconciliation
safety precedes provider transport
provider health channels are independent
provider errors are sanitized
~~~

## Provider fixture

The ProviderFixture protocol exposes only common qualification hooks:

~~~text
provider_manifest
build_runtime
build_execution_adapter
build_snapshot_adapter
paper_account_fixture
cleanup
~~~

Execution uses the existing ExecutionPort. Reconciliation uses the existing BrokerSnapshotPort. LOT-01 does not create provider-specific copies of those ports.

## Architecture fitness functions

LOT-01 adds FF-048 through FF-056.

They protect:

- provider SDK confinement;
- compliance-core independence from concrete adapters;
- absence of concrete provider branching in Domain, OMS, Risk, Portfolio, Reconciliation and Safety;
- separation between canonical IDs and provider evidence.

## Version policy

~~~text
0.8       BrokerAdapterContract v1 candidate
0.9       compatibility freeze
1.0       stable BrokerAdapterContract v1
~~~

The initial candidate identity is 1.0-rc1.

## Explicit non-goals

LOT-01 does not implement:

- IBKR SDK or session handling;
- IBKR mappings;
- Alpaca compliance certification;
- compliance scenarios or evidence capture;
- compliance reports;
- CertifiedCapability;
- broker-specific reconciliation;
- LIVE trading.

Those concerns belong to later 0.8 LOTs.
