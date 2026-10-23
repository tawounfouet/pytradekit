"""Executable compliance scenario metadata."""

from __future__ import annotations

from dataclasses import dataclass

from ._validation import normalized_texts, required_text
from .capability import BrokerCapability
from .requirement import ComplianceEvidenceType


@dataclass(frozen=True, slots=True)
class ComplianceScenario:
    """Provider-neutral scenario definition consumed by ComplianceHarness."""

    scenario_id: str
    capability: BrokerCapability
    preconditions: tuple[str, ...]
    action: str
    expected_result: str
    failure_semantics: str
    cleanup: str
    required_evidence: tuple[ComplianceEvidenceType, ...]
    requirement_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_id",
            required_text(self.scenario_id, field_name="scenario_id"),
        )
        if not isinstance(self.capability, BrokerCapability):
            raise ValueError("capability must be a BrokerCapability.")
        object.__setattr__(
            self,
            "preconditions",
            normalized_texts(self.preconditions, field_name="preconditions"),
        )
        object.__setattr__(self, "action", required_text(self.action, field_name="action"))
        object.__setattr__(
            self,
            "expected_result",
            required_text(self.expected_result, field_name="expected_result"),
        )
        object.__setattr__(
            self,
            "failure_semantics",
            required_text(self.failure_semantics, field_name="failure_semantics"),
        )
        object.__setattr__(
            self,
            "cleanup",
            required_text(self.cleanup, field_name="cleanup"),
        )
        if not self.required_evidence:
            raise ValueError("required_evidence must not be empty.")
        if any(
            not isinstance(value, ComplianceEvidenceType)
            for value in self.required_evidence
        ):
            raise ValueError("required_evidence values must be ComplianceEvidenceType.")
        if len(set(self.required_evidence)) != len(self.required_evidence):
            raise ValueError("required_evidence values must be unique.")
        object.__setattr__(
            self,
            "requirement_ids",
            normalized_texts(self.requirement_ids, field_name="requirement_ids"),
        )
        if not self.requirement_ids:
            raise ValueError("requirement_ids must not be empty.")
