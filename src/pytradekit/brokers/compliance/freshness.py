"""Stale evidence policy for capability certification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from pytradekit.shared import require_utc_datetime

from .evidence import ComplianceEvidence
from .manifest import ProviderCapabilityManifest
from .version import ContractVersion


def _environment_value(environment: object) -> str:
    return str(getattr(environment, "value", environment))


class EvidenceFreshnessReason(StrEnum):
    """Why retained compliance evidence is no longer current."""

    PROVIDER_MISMATCH = "PROVIDER_MISMATCH"
    ENVIRONMENT_MISMATCH = "ENVIRONMENT_MISMATCH"
    ADAPTER_VERSION_MISMATCH = "ADAPTER_VERSION_MISMATCH"
    SDK_MISMATCH = "SDK_MISMATCH"
    CONTRACT_VERSION_MISMATCH = "CONTRACT_VERSION_MISMATCH"
    COMMIT_MISMATCH = "COMMIT_MISMATCH"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class EvidenceFreshness:
    """Current/stale decision with explicit invalidation reasons."""

    reasons: tuple[EvidenceFreshnessReason, ...]

    @property
    def is_current(self) -> bool:
        """Return whether evidence remains valid for certification."""

        return not self.reasons


@dataclass(frozen=True, slots=True)
class StaleEvidencePolicy:
    """Invalidate evidence after material adapter, SDK, contract, or age changes."""

    max_age: timedelta | None = None
    require_same_commit: bool = False

    def __post_init__(self) -> None:
        if self.max_age is not None and self.max_age <= timedelta(0):
            raise ValueError("max_age must be positive when configured.")
        if type(self.require_same_commit) is not bool:
            raise ValueError("require_same_commit must be a bool.")

    def evaluate(
        self,
        evidence: ComplianceEvidence,
        *,
        manifest: ProviderCapabilityManifest,
        contract_version: ContractVersion,
        now: datetime,
        expected_commit: str | None = None,
    ) -> EvidenceFreshness:
        """Evaluate whether retained evidence still matches the active runtime contract."""

        current_time = require_utc_datetime(
            now,
            field_name="StaleEvidencePolicy now",
        )
        reasons: list[EvidenceFreshnessReason] = []

        if evidence.provider != manifest.provider:
            reasons.append(EvidenceFreshnessReason.PROVIDER_MISMATCH)
        if _environment_value(evidence.environment) != _environment_value(
            manifest.environment
        ):
            reasons.append(EvidenceFreshnessReason.ENVIRONMENT_MISMATCH)
        if evidence.adapter_version != manifest.adapter_version:
            reasons.append(EvidenceFreshnessReason.ADAPTER_VERSION_MISMATCH)
        if (evidence.sdk_name, evidence.sdk_version) != (
            manifest.sdk_name,
            manifest.sdk_version,
        ):
            reasons.append(EvidenceFreshnessReason.SDK_MISMATCH)
        if evidence.contract_version != contract_version:
            reasons.append(EvidenceFreshnessReason.CONTRACT_VERSION_MISMATCH)
        if self.require_same_commit and (
            expected_commit is None or evidence.commit_sha != expected_commit
        ):
            reasons.append(EvidenceFreshnessReason.COMMIT_MISMATCH)
        if (
            self.max_age is not None
            and current_time - evidence.captured_at > self.max_age
        ):
            reasons.append(EvidenceFreshnessReason.EXPIRED)

        return EvidenceFreshness(reasons=tuple(dict.fromkeys(reasons)))
