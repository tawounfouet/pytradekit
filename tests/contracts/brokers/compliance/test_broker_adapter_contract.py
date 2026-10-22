"""Public contract tests for the 0.8 BrokerAdapterContract candidate."""

from pytradekit.brokers.compliance import (
    ALL_BROKER_CONTRACT_DIMENSIONS,
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
    BROKER_CAPABILITY_CATALOG,
    BROKER_CONTRACT_INVARIANTS,
    BrokerCapability,
    BrokerContractDimension,
    BrokerContractInvariant,
)


def test_candidate_contract_has_complete_declared_dimensions() -> None:
    contract = BROKER_ADAPTER_CONTRACT_V1_CANDIDATE

    assert str(contract.version) == "1.0-rc1"
    assert contract.version.is_candidate
    assert contract.dimensions == ALL_BROKER_CONTRACT_DIMENSIONS
    assert contract.capability_catalog == BROKER_CAPABILITY_CATALOG
    assert contract.invariants == BROKER_CONTRACT_INVARIANTS


def test_contract_contains_required_semantic_boundaries() -> None:
    contract = BROKER_ADAPTER_CONTRACT_V1_CANDIDATE

    assert BrokerContractDimension.IDENTITY in contract.dimensions
    assert BrokerContractDimension.EXECUTION in contract.dimensions
    assert BrokerContractDimension.RECONCILIATION in contract.dimensions
    assert BrokerContractDimension.SAFETY in contract.dimensions
    assert BrokerContractDimension.EVIDENCE in contract.dimensions

    assert BrokerCapability.MARKET_ORDER in contract.capability_catalog
    assert BrokerCapability.LIMIT_ORDER in contract.capability_catalog
    assert BrokerCapability.CANCEL_ORDER in contract.capability_catalog
    assert BrokerCapability.RECONNECT_RECOVERY in contract.capability_catalog


def test_contract_encodes_cross_provider_safety_invariants() -> None:
    invariants = BROKER_ADAPTER_CONTRACT_V1_CANDIDATE.invariants

    assert BrokerContractInvariant.CANONICAL_IDS_LOCAL in invariants
    assert BrokerContractInvariant.PROVIDER_IDS_EXTERNAL_EVIDENCE in invariants
    assert BrokerContractInvariant.NO_BLIND_ECONOMIC_WRITE_RETRY in invariants
    assert BrokerContractInvariant.SAFETY_PRECEDES_TRANSPORT in invariants
    assert BrokerContractInvariant.RECONNECT_REQUIRES_RECONCILIATION in invariants


def test_contract_taxonomy_contains_no_concrete_provider_name() -> None:
    values = [
        *(capability.value.lower() for capability in BROKER_CAPABILITY_CATALOG),
        *(dimension.value.lower() for dimension in ALL_BROKER_CONTRACT_DIMENSIONS),
        *(invariant.value.lower() for invariant in BROKER_CONTRACT_INVARIANTS),
    ]

    assert all("alpaca" not in value for value in values)
    assert all("ibkr" not in value for value in values)
