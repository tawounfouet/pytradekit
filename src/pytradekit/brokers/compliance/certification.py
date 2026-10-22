"""Certified broker capability records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.runtime.configuration import RuntimeEnvironment
from pytradekit.shared import require_utc_datetime

from ._validation import normalized_texts, required_text
from .capability import BrokerCapability, CapabilityConstraint
from .certification_level import CertificationLevel
from .version import ContractVersion


@dataclass(frozen=True, slots=True)
class CertifiedCapability:
    """Capability-specific qualification record backed by retained evidence."""

    provider: str
    environment: RuntimeEnvironment
    capability: BrokerCapability
    certification_level: CertificationLevel
    contract_version: ContractVersion
    qualified_at: datetime
    evidence_refs: tuple[str, ...]
    known_limitations: tuple[str, ...]
    constraints: CapabilityConstraint
    qualified_commit: str
    adapter_version: str
    sdk_name: str | None = None
    sdk_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider",
            required_text(self.provider, field_name="provider").lower(),
        )
        if not isinstance(self.environment, RuntimeEnvironment):
            raise ValueError("environment must be a RuntimeEnvironment.")
        if not isinstance(self.capability, BrokerCapability):
            raise ValueError("capability must be a BrokerCapability.")
        if not isinstance(self.certification_level, CertificationLevel):
            raise ValueError("certification_level must be a CertificationLevel.")
        if not isinstance(self.contract_version, ContractVersion):
            raise ValueError("contract_version must be a ContractVersion.")
        require_utc_datetime(
            self.qualified_at,
            field_name="CertifiedCapability qualified_at",
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalized_texts(self.evidence_refs, field_name="evidence_refs"),
        )
        if self.certification_level > CertificationLevel.C0_DEFINED:
            if not self.evidence_refs:
                raise ValueError("Qualified capabilities above C0 require evidence_refs.")
        object.__setattr__(
            self,
            "known_limitations",
            normalized_texts(
                self.known_limitations,
                field_name="known_limitations",
            ),
        )
        if not isinstance(self.constraints, CapabilityConstraint):
            raise ValueError("constraints must be a CapabilityConstraint.")
        object.__setattr__(
            self,
            "qualified_commit",
            required_text(self.qualified_commit, field_name="qualified_commit"),
        )
        object.__setattr__(
            self,
            "adapter_version",
            required_text(self.adapter_version, field_name="adapter_version"),
        )
        if (self.sdk_name is None) != (self.sdk_version is None):
            raise ValueError("sdk_name and sdk_version must be declared together.")
        if self.sdk_name is not None:
            object.__setattr__(
                self,
                "sdk_name",
                required_text(self.sdk_name, field_name="sdk_name"),
            )
        if self.sdk_version is not None:
            object.__setattr__(
                self,
                "sdk_version",
                required_text(self.sdk_version, field_name="sdk_version"),
            )

    def to_dict(self) -> dict[str, object]:
        """Return a stable registry/report representation."""

        return {
            "provider": self.provider,
            "environment": self.environment.value,
            "capability": self.capability.value,
            "certification_level": self.certification_level.code,
            "contract_version": str(self.contract_version),
            "qualified_at": self.qualified_at.isoformat(),
            "evidence_refs": list(self.evidence_refs),
            "known_limitations": list(self.known_limitations),
            "constraints": {
                "asset_classes": sorted(
                    value.value for value in self.constraints.asset_classes
                ),
                "order_types": sorted(
                    value.value for value in self.constraints.order_types
                ),
                "time_in_force": sorted(
                    value.value for value in self.constraints.time_in_force
                ),
                "environments": sorted(
                    value.value for value in self.constraints.environments
                ),
                "account_modes": sorted(self.constraints.account_modes),
                "required_settings": list(self.constraints.required_settings),
                "notes": list(self.constraints.notes),
            },
            "qualified_commit": self.qualified_commit,
            "adapter_version": self.adapter_version,
            "sdk": (
                None
                if self.sdk_name is None
                else {"name": self.sdk_name, "version": self.sdk_version}
            ),
        }
