"""Static certification registry for broker capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from pytradekit.runtime.configuration import RuntimeEnvironment

from .capability import BrokerCapability
from .certification import CertifiedCapability
from .evidence import ComplianceEvidence
from .freshness import StaleEvidencePolicy
from .manifest import ProviderCapabilityManifest
from .report import ComplianceReport
from .version import ContractVersion


@dataclass(frozen=True, slots=True)
class CertificationRegistry:
    """Immutable generated registry of capability certification records."""

    entries: tuple[CertifiedCapability, ...]

    def __post_init__(self) -> None:
        keys: set[tuple[str, RuntimeEnvironment, BrokerCapability, str]] = set()
        for entry in self.entries:
            key = (
                entry.provider,
                entry.environment,
                entry.capability,
                str(entry.contract_version),
            )
            if key in keys:
                raise ValueError("CertificationRegistry contains duplicate capability records.")
            keys.add(key)

    @classmethod
    def from_report(cls, report: ComplianceReport) -> CertificationRegistry:
        """Build a static registry from one qualification report."""

        return cls(entries=report.capability_results)

    def find(
        self,
        *,
        provider: str,
        environment: RuntimeEnvironment,
        capability: BrokerCapability,
        contract_version: ContractVersion,
    ) -> CertifiedCapability | None:
        """Find one exact provider capability certification."""

        normalized_provider = provider.strip().lower()
        for entry in self.entries:
            if (
                entry.provider == normalized_provider
                and entry.environment is environment
                and entry.capability is capability
                and entry.contract_version == contract_version
            ):
                return entry
        return None

    def find_current(
        self,
        *,
        provider: str,
        environment: RuntimeEnvironment,
        capability: BrokerCapability,
        contract_version: ContractVersion,
        manifest: ProviderCapabilityManifest,
        evidence_by_ref: Mapping[str, ComplianceEvidence],
        stale_policy: StaleEvidencePolicy,
        now: datetime,
        expected_commit: str | None = None,
    ) -> CertifiedCapability | None:
        """Return certification only when every retained evidence reference is current."""

        entry = self.find(
            provider=provider,
            environment=environment,
            capability=capability,
            contract_version=contract_version,
        )
        if entry is None:
            return None
        for evidence_ref in entry.evidence_refs:
            evidence = evidence_by_ref.get(evidence_ref)
            if evidence is None:
                return None
            freshness = stale_policy.evaluate(
                evidence,
                manifest=manifest,
                contract_version=contract_version,
                now=now,
                expected_commit=expected_commit,
            )
            if not freshness.is_current:
                return None
        return entry

    def to_dict(self) -> dict[str, object]:
        """Return deterministic generated registry content."""

        ordered = sorted(
            self.entries,
            key=lambda entry: (
                entry.provider,
                entry.environment.value,
                entry.capability.value,
                str(entry.contract_version),
            ),
        )
        return {"certifications": [entry.to_dict() for entry in ordered]}
