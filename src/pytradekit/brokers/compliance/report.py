"""Provider compliance reports and deterministic report generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.runtime.configuration import RuntimeEnvironment
from pytradekit.shared import require_utc_datetime

from ._validation import normalized_texts, required_text
from .certification import CertifiedCapability
from .evidence import ComplianceEvidence
from .manifest import ProviderCapabilityManifest
from .result import ComplianceResult, ComplianceStatus
from .version import ContractVersion


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """Complete provider qualification report for one exact run."""

    provider: str
    environment: RuntimeEnvironment
    adapter_version: str
    commit_sha: str
    manifest_version: str
    contract_version: ContractVersion
    scenario_results: tuple[ComplianceResult, ...]
    capability_results: tuple[CertifiedCapability, ...]
    known_limitations: tuple[str, ...]
    waivers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        provider = required_text(self.provider, field_name="provider").lower()
        object.__setattr__(self, "provider", provider)
        if not isinstance(self.environment, RuntimeEnvironment):
            raise ValueError("environment must be a RuntimeEnvironment.")
        object.__setattr__(
            self,
            "adapter_version",
            required_text(self.adapter_version, field_name="adapter_version"),
        )
        object.__setattr__(
            self,
            "commit_sha",
            required_text(self.commit_sha, field_name="commit_sha"),
        )
        object.__setattr__(
            self,
            "manifest_version",
            required_text(self.manifest_version, field_name="manifest_version"),
        )
        if not isinstance(self.contract_version, ContractVersion):
            raise ValueError("contract_version must be a ContractVersion.")
        if not self.scenario_results:
            raise ValueError("scenario_results must not be empty.")
        for result in self.scenario_results:
            if result.provider != provider or result.environment is not self.environment:
                raise ValueError("scenario result provider/environment mismatch.")
        for capability in self.capability_results:
            if (
                capability.provider != provider
                or capability.environment is not self.environment
            ):
                raise ValueError("capability result provider/environment mismatch.")
        object.__setattr__(
            self,
            "known_limitations",
            normalized_texts(
                self.known_limitations,
                field_name="known_limitations",
            ),
        )
        object.__setattr__(
            self,
            "waivers",
            normalized_texts(self.waivers, field_name="waivers"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalized_texts(self.evidence_refs, field_name="evidence_refs"),
        )
        require_utc_datetime(
            self.generated_at,
            field_name="ComplianceReport generated_at",
        )

    @property
    def complete(self) -> bool:
        """Return whether no required scenario is failed or blocked."""

        return all(
            result.status not in {ComplianceStatus.FAIL, ComplianceStatus.BLOCKED}
            for result in self.scenario_results
        )

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready report."""

        return {
            "provider": self.provider,
            "environment": self.environment.value,
            "adapter_version": self.adapter_version,
            "commit": self.commit_sha,
            "manifest_version": self.manifest_version,
            "contract_version": str(self.contract_version),
            "scenario_results": [
                result.to_dict() for result in self.scenario_results
            ],
            "capability_results": [
                capability.to_dict() for capability in self.capability_results
            ],
            "known_limitations": list(self.known_limitations),
            "waivers": list(self.waivers),
            "evidence_refs": list(self.evidence_refs),
            "generated_at": self.generated_at.isoformat(),
            "complete": self.complete,
        }


class ComplianceReportGenerator:
    """Build one report from a manifest, scenario results, and retained evidence."""

    def generate(
        self,
        *,
        manifest: ProviderCapabilityManifest,
        commit_sha: str,
        manifest_version: str,
        contract_version: ContractVersion,
        scenario_results: tuple[ComplianceResult, ...],
        capability_results: tuple[CertifiedCapability, ...],
        evidence: tuple[ComplianceEvidence, ...],
        generated_at: datetime,
        waivers: tuple[str, ...] = (),
    ) -> ComplianceReport:
        """Generate an immutable provider compliance report."""

        evidence_refs = tuple(item.evidence_id for item in evidence)
        return ComplianceReport(
            provider=manifest.provider,
            environment=manifest.environment,
            adapter_version=manifest.adapter_version,
            commit_sha=commit_sha,
            manifest_version=manifest_version,
            contract_version=contract_version,
            scenario_results=scenario_results,
            capability_results=capability_results,
            known_limitations=manifest.known_limitations,
            waivers=waivers,
            evidence_refs=evidence_refs,
            generated_at=generated_at,
        )
