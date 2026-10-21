"""Maximum daily loss rule."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.risk.domain import RiskContext, RiskDecision, RiskViolation
from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class DailyLoss:
    """Halt risk-increasing activity when daily loss reaches the configured fraction."""

    maximum_loss_fraction: Decimal

    @property
    def decision(self) -> RiskDecision:
        return RiskDecision.HALT

    def __post_init__(self) -> None:
        if (
            not self.maximum_loss_fraction.is_finite()
            or self.maximum_loss_fraction <= 0
            or self.maximum_loss_fraction >= 1
        ):
            raise DomainValidationError(
                "DailyLoss maximum_loss_fraction must be between zero and one."
            )

    def evaluate(self, context: RiskContext) -> RiskViolation | None:
        baseline = context.start_of_day_nav
        if baseline is None or baseline.amount <= 0:
            return RiskViolation(
                code="DAILY_LOSS_INPUT_UNAVAILABLE",
                message="Daily loss requires a positive start-of-day NAV.",
                observed_value=context.current.nav,
                limit_value=self.maximum_loss_fraction,
                scope=context.scope,
            )
        if baseline.currency != context.current.nav.currency:
            return RiskViolation(
                code="DAILY_LOSS_CURRENCY_MISMATCH",
                message="Daily loss NAV currencies do not match.",
                observed_value=context.current.nav,
                limit_value=self.maximum_loss_fraction,
                scope=context.scope,
            )

        loss_fraction = (baseline.amount - context.current.nav.amount) / baseline.amount
        if loss_fraction >= self.maximum_loss_fraction:
            return RiskViolation(
                code="MAX_DAILY_LOSS_EXCEEDED",
                message="Current daily loss reaches or exceeds the configured maximum.",
                observed_value=loss_fraction,
                limit_value=self.maximum_loss_fraction,
                scope=context.scope,
            )
        return None
