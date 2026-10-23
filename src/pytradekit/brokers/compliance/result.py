"""Compliance scenario results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pytradekit.runtime.configuration import RuntimeEnvironment
from pytradekit.shared import require_utc_datetime

from ._validation import normalized_texts, required_text


class ComplianceStatus(StrEnum):
    """Explicit outcome of one compliance scenario."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class ComplianceResult:
    """Outcome record for one scenario execution."""

    scenario_id: str
    status: ComplianceStatus
    started_at: datetime
    completed_at: datetime
    provider: str
    environment: RuntimeEnvironment
    evidence_refs: tuple[str, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_id",
            required_text(self.scenario_id, field_name="scenario_id"),
        )
        if not isinstance(self.status, ComplianceStatus):
            raise ValueError("status must be a ComplianceStatus.")
        start = require_utc_datetime(
            self.started_at,
            field_name="ComplianceResult started_at",
        )
        end = require_utc_datetime(
            self.completed_at,
            field_name="ComplianceResult completed_at",
        )
        if end < start:
            raise ValueError("ComplianceResult completed_at cannot precede started_at.")
        object.__setattr__(
            self,
            "provider",
            required_text(self.provider, field_name="provider").lower(),
        )
        if not isinstance(self.environment, RuntimeEnvironment):
            raise ValueError("environment must be a RuntimeEnvironment.")
        object.__setattr__(
            self,
            "evidence_refs",
            normalized_texts(self.evidence_refs, field_name="evidence_refs"),
        )
        if self.status is ComplianceStatus.PASS and not self.evidence_refs:
            raise ValueError("PASS results must reference retained evidence.")
        if self.status is not ComplianceStatus.PASS and self.reason is None:
            raise ValueError("Non-PASS results require a reason.")
        if self.reason is not None:
            object.__setattr__(
                self,
                "reason",
                required_text(self.reason, field_name="reason"),
            )

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready result representation."""

        return {
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "provider": self.provider,
            "environment": self.environment.value,
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
        }
