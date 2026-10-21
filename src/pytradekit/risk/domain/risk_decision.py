"""Risk decisions."""

from enum import StrEnum


class RiskDecision(StrEnum):
    """Canonical outcome of a risk evaluation."""

    ALLOW = "allow"
    WARN = "warn"
    REJECT = "reject"
    HALT = "halt"


_DECISION_RANK = {
    RiskDecision.ALLOW: 0,
    RiskDecision.WARN: 1,
    RiskDecision.REJECT: 2,
    RiskDecision.HALT: 3,
}


def most_restrictive(*decisions: RiskDecision) -> RiskDecision:
    """Return the most restrictive decision."""
    if not decisions:
        return RiskDecision.ALLOW
    return max(decisions, key=_DECISION_RANK.__getitem__)
