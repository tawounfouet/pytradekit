"""Immutable risk evaluation."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.risk.domain.risk_decision import RiskDecision
from pytradekit.risk.domain.risk_policy_id import RiskPolicyId
from pytradekit.risk.domain.risk_violation import RiskViolation
from pytradekit.shared import require_utc_datetime


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    """Evaluation of one versioned policy."""

    decision: RiskDecision
    violations: tuple[RiskViolation, ...]
    evaluated_at: datetime
    policy_id: RiskPolicyId
    policy_version: int

    def __post_init__(self) -> None:
        require_utc_datetime(self.evaluated_at, field_name="RiskEvaluation evaluated_at")
