"""Risk limit contract."""

from typing import Protocol

from pytradekit.risk.domain.risk_context import RiskContext
from pytradekit.risk.domain.risk_decision import RiskDecision
from pytradekit.risk.domain.risk_violation import RiskViolation


class RiskLimit(Protocol):
    """Pure policy rule contract."""

    @property
    def decision(self) -> RiskDecision:
        """Return the decision produced when the rule is violated."""
        ...

    def evaluate(self, context: RiskContext) -> RiskViolation | None:
        """Return a violation or None without side effects."""
        ...
