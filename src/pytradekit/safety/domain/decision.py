"""Explicit explainable safety decisions."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.safety.domain.enums import SafetyAction, SafetyReason, SafetyState
from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    """One deterministic safety evaluation result."""

    allowed: bool
    state: SafetyState
    action: SafetyAction
    reason_codes: tuple[SafetyReason, ...]
    evaluated_at: datetime
    risk_override_applied: bool = False

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise DomainValidationError("SafetyDecision allowed must be a bool.")
        if not isinstance(self.state, SafetyState):
            raise DomainValidationError("SafetyDecision state must be a SafetyState.")
        if not isinstance(self.action, SafetyAction):
            raise DomainValidationError("SafetyDecision action must be a SafetyAction.")
        if not self.reason_codes:
            raise DomainValidationError("SafetyDecision requires at least one reason code.")
        if any(not isinstance(code, SafetyReason) for code in self.reason_codes):
            raise DomainValidationError("SafetyDecision contains an invalid reason code.")
        require_utc_datetime(
            self.evaluated_at,
            field_name="SafetyDecision evaluated_at",
        )
