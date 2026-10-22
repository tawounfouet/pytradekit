"""Sanitized, version-linked broker compliance evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from pytradekit.runtime.configuration import RuntimeEnvironment
from pytradekit.shared import require_utc_datetime

from ._validation import required_text
from .requirement import ComplianceEvidenceType
from .version import ContractVersion


@dataclass(frozen=True, slots=True)
class ComplianceEvidence:
    """Retained sanitized evidence for one exact provider qualification scenario."""

    evidence_id: str
    scenario_id: str
    provider: str
    environment: RuntimeEnvironment
    commit_sha: str
    adapter_version: str
    contract_version: ContractVersion
    evidence_type: ComplianceEvidenceType
    captured_at: datetime
    payload: Mapping[str, object]
    sdk_name: str | None = None
    sdk_version: str | None = None
    artifact_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_id",
            required_text(self.evidence_id, field_name="evidence_id"),
        )
        object.__setattr__(
            self,
            "scenario_id",
            required_text(self.scenario_id, field_name="scenario_id"),
        )
        object.__setattr__(
            self,
            "provider",
            required_text(self.provider, field_name="provider").lower(),
        )
        if not isinstance(self.environment, RuntimeEnvironment):
            raise ValueError("environment must be a RuntimeEnvironment.")
        object.__setattr__(
            self,
            "commit_sha",
            required_text(self.commit_sha, field_name="commit_sha"),
        )
        object.__setattr__(
            self,
            "adapter_version",
            required_text(self.adapter_version, field_name="adapter_version"),
        )
        if not isinstance(self.contract_version, ContractVersion):
            raise ValueError("contract_version must be a ContractVersion.")
        if not isinstance(self.evidence_type, ComplianceEvidenceType):
            raise ValueError("evidence_type must be a ComplianceEvidenceType.")
        require_utc_datetime(
            self.captured_at,
            field_name="ComplianceEvidence captured_at",
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
        if self.artifact_ref is not None:
            object.__setattr__(
                self,
                "artifact_ref",
                required_text(self.artifact_ref, field_name="artifact_ref"),
            )
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready evidence representation."""

        return {
            "evidence_id": self.evidence_id,
            "scenario_id": self.scenario_id,
            "provider": self.provider,
            "environment": self.environment.value,
            "commit_sha": self.commit_sha,
            "adapter_version": self.adapter_version,
            "contract_version": str(self.contract_version),
            "evidence_type": self.evidence_type.value,
            "captured_at": self.captured_at.isoformat(),
            "sdk": (
                None
                if self.sdk_name is None
                else {"name": self.sdk_name, "version": self.sdk_version}
            ),
            "artifact_ref": self.artifact_ref,
            "payload": _copy_json_value(dict(self.payload)),
        }


def _copy_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _copy_json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_copy_json_value(item) for item in value]
    return value
