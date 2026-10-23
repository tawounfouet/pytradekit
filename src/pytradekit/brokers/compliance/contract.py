"""Candidate broker adapter contract for milestone 0.8 LOT-01."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .capability import BROKER_CAPABILITY_CATALOG, BrokerCapability
from .manifest import ProviderCapabilityManifest
from .version import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
    ContractVersion,
)


class BrokerContractDimension(StrEnum):
    """Provider-neutral dimensions covered by the candidate contract."""

    IDENTITY = "identity"
    CAPABILITIES = "capabilities"
    EXECUTION = "execution"
    QUERY = "query"
    CANCELLATION = "cancellation"
    FACTS_EVENTS = "facts_events"
    SNAPSHOTS = "snapshots"
    ERRORS = "errors"
    UNCERTAINTY = "uncertainty"
    RECONNECT = "reconnect"
    RECONCILIATION = "reconciliation"
    READINESS = "readiness"
    SECURITY = "security"
    SAFETY = "safety"
    HEALTH = "health"
    EVIDENCE = "evidence"


class BrokerContractInvariant(StrEnum):
    """Cross-provider invariants that adapters must preserve."""

    NORMALIZE_SEMANTICS_NOT_FEATURES = "normalize_semantics_not_features"
    CANONICAL_IDS_LOCAL = "canonical_ids_local"
    PROVIDER_IDS_EXTERNAL_EVIDENCE = "provider_ids_external_evidence"
    NO_BLIND_ECONOMIC_WRITE_RETRY = "no_blind_economic_write_retry"
    UNCERTAIN_OUTCOME_REQUIRES_RECONCILIATION = (
        "uncertain_outcome_requires_reconciliation"
    )
    CANCEL_ACK_IS_NOT_TERMINAL_FACT = "cancel_ack_is_not_terminal_fact"
    EXECUTION_FACT_HAS_STABLE_IDENTITY = "execution_fact_has_stable_identity"
    RECONNECT_REQUIRES_RECONCILIATION = "reconnect_requires_reconciliation"
    SAFETY_PRECEDES_TRANSPORT = "safety_precedes_transport"
    CHANNEL_HEALTH_IS_INDEPENDENT = "channel_health_is_independent"
    PROVIDER_ERRORS_ARE_SANITIZED = "provider_errors_are_sanitized"


ALL_BROKER_CONTRACT_DIMENSIONS: frozenset[BrokerContractDimension] = frozenset(
    BrokerContractDimension
)

BROKER_CONTRACT_INVARIANTS: frozenset[BrokerContractInvariant] = frozenset(
    BrokerContractInvariant
)


@dataclass(frozen=True, slots=True)
class BrokerAdapterContract:
    """Versioned provider-neutral contract candidate for broker adapters."""

    version: ContractVersion
    dimensions: frozenset[BrokerContractDimension]
    capability_catalog: frozenset[BrokerCapability]
    invariants: frozenset[BrokerContractInvariant]

    def __post_init__(self) -> None:
        if not isinstance(self.version, ContractVersion):
            raise ValueError("version must be a ContractVersion.")
        if not self.dimensions:
            raise ValueError("dimensions must not be empty.")
        if not self.capability_catalog:
            raise ValueError("capability_catalog must not be empty.")
        if not self.invariants:
            raise ValueError("invariants must not be empty.")

    @classmethod
    def candidate_v1(cls) -> BrokerAdapterContract:
        """Build the complete 0.8 candidate contract."""

        return cls(
            version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
            dimensions=ALL_BROKER_CONTRACT_DIMENSIONS,
            capability_catalog=BROKER_CAPABILITY_CATALOG,
            invariants=BROKER_CONTRACT_INVARIANTS,
        )

    def validate_manifest(self, manifest: ProviderCapabilityManifest) -> None:
        """Reject capability declarations outside this contract taxonomy."""

        unknown = manifest.capability_set - self.capability_catalog
        if unknown:
            names = ", ".join(sorted(capability.value for capability in unknown))
            raise ValueError(f"Manifest declares capabilities outside the contract: {names}.")


BROKER_ADAPTER_CONTRACT_V1_CANDIDATE = BrokerAdapterContract.candidate_v1()
