"""Maximum gross exposure rule."""

from dataclasses import dataclass

from pytradekit.risk.domain import RiskContext, RiskDecision, RiskViolation
from pytradekit.shared import DomainValidationError, Money


@dataclass(frozen=True, slots=True)
class MaxGrossExposure:
    """Reject a projected portfolio above maximum gross exposure."""

    maximum: Money

    @property
    def decision(self) -> RiskDecision:
        return RiskDecision.REJECT

    def __post_init__(self) -> None:
        if self.maximum.amount <= 0:
            raise DomainValidationError("MaxGrossExposure maximum must be positive.")

    def evaluate(self, context: RiskContext) -> RiskViolation | None:
        observed = context.projected.gross_exposure
        if observed.currency != self.maximum.currency:
            return RiskViolation(
                code="GROSS_EXPOSURE_CURRENCY_MISMATCH",
                message="Gross exposure currency does not match the configured limit.",
                observed_value=observed,
                limit_value=self.maximum,
                scope=context.scope,
            )
        if observed > self.maximum:
            return RiskViolation(
                code="MAX_GROSS_EXPOSURE_EXCEEDED",
                message="Projected gross exposure exceeds the configured maximum.",
                observed_value=observed,
                limit_value=self.maximum,
                scope=context.scope,
            )
        return None
