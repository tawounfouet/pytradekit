"""Compliance requirements and qualification evidence categories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ._validation import required_text
from .capability import BrokerCapability
from .certification_level import CertificationLevel


class ComplianceCriticality(StrEnum):
    """Severity of a violated broker compliance requirement."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ComplianceEvidenceType(StrEnum):
    """Evidence classes used to support capability qualification."""

    DEFINITION = "DEFINITION"
    IMPLEMENTATION = "IMPLEMENTATION"
    INTEGRATION = "INTEGRATION"
    PAPER = "PAPER"
    LIVE = "LIVE"
    DIAGNOSTIC = "DIAGNOSTIC"


@dataclass(frozen=True, slots=True)
class ComplianceRequirement:
    """One capability-specific requirement in the broker compliance contract."""

    requirement_id: str
    capability: BrokerCapability
    level: CertificationLevel
    description: str
    criticality: ComplianceCriticality
    applicable: bool
    evidence_type: ComplianceEvidenceType

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requirement_id",
            required_text(self.requirement_id, field_name="requirement_id"),
        )
        object.__setattr__(
            self,
            "description",
            required_text(self.description, field_name="description"),
        )
        if not isinstance(self.capability, BrokerCapability):
            raise ValueError("capability must be a BrokerCapability.")
        if not isinstance(self.level, CertificationLevel):
            raise ValueError("level must be a CertificationLevel.")
        if not isinstance(self.criticality, ComplianceCriticality):
            raise ValueError("criticality must be a ComplianceCriticality.")
        if type(self.applicable) is not bool:
            raise ValueError("applicable must be a bool.")
        if not isinstance(self.evidence_type, ComplianceEvidenceType):
            raise ValueError("evidence_type must be a ComplianceEvidenceType.")
        if (
            self.level is CertificationLevel.C3_PAPER_QUALIFIED
            and self.evidence_type is not ComplianceEvidenceType.PAPER
        ):
            raise ValueError("C3 requirements must require PAPER evidence.")
        if (
            self.level >= CertificationLevel.C4_LIVE_LIMITED
            and self.evidence_type is not ComplianceEvidenceType.LIVE
        ):
            raise ValueError("C4 and C5 requirements must require LIVE evidence.")
