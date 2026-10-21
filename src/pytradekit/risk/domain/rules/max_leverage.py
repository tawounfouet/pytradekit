"""Maximum leverage rule."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.risk.domain import RiskContext, RiskDecision, RiskViolation
from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class MaxLeverage:
    """Reject projected leverage above the configured multiple."""

    maximum: Decimal

    @property
    def decision(self) -> RiskDecision:
        return RiskDecision.REJECT

    def __post_init__(self) -> None:
        if not self.maximum.is_finite() or self.maximum <= 0:
            raise DomainValidationError("MaxLeverage maximum must be positive.")

    def evaluate(self, context: RiskContext) -> RiskViolation | None:
        observed = context.projected.leverage
        if observed is None:
            return RiskViolation(
                code="LEVERAGE_UNAVAILABLE",
                message="Projected leverage cannot be computed from a non-positive NAV.",
                observed_value=context.projected.nav,
                limit_value=self.maximum,
                scope=context.scope,
            )
        if observed > self.maximum:
            return RiskViolation(
                code="MAX_LEVERAGE_EXCEEDED",
                message="Projected leverage exceeds the configured maximum.",
                observed_value=observed,
                limit_value=self.maximum,
                scope=context.scope,
            )
        return None
