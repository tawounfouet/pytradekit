"""Maximum projected position size rule."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.risk.domain import RiskContext, RiskDecision, RiskViolation
from pytradekit.shared import DomainValidationError, Money


@dataclass(frozen=True, slots=True)
class MaxPositionSize:
    """Reject a projected absolute position above configured quantity or notional."""

    max_quantity: Decimal
    max_notional: Money | None = None

    @property
    def decision(self) -> RiskDecision:
        return RiskDecision.REJECT

    def __post_init__(self) -> None:
        if not self.max_quantity.is_finite() or self.max_quantity <= 0:
            raise DomainValidationError("MaxPositionSize max_quantity must be positive.")
        if self.max_notional is not None and self.max_notional.amount <= 0:
            raise DomainValidationError("MaxPositionSize max_notional must be positive.")

    def evaluate(self, context: RiskContext) -> RiskViolation | None:
        observed_quantity = abs(context.projected.projected_position_quantity)
        if observed_quantity > self.max_quantity:
            return RiskViolation(
                code="MAX_POSITION_SIZE_EXCEEDED",
                message="Projected absolute position quantity exceeds the maximum.",
                observed_value=observed_quantity,
                limit_value=self.max_quantity,
                scope=context.scope,
            )

        if self.max_notional is not None:
            observed_notional = Money(
                observed_quantity * context.order.reference_price.value,
                context.order.reference_price.currency,
            )
            if observed_notional.currency != self.max_notional.currency:
                return RiskViolation(
                    code="POSITION_CURRENCY_MISMATCH",
                    message="Projected position currency does not match the configured limit.",
                    observed_value=observed_notional,
                    limit_value=self.max_notional,
                    scope=context.scope,
                )
            if observed_notional > self.max_notional:
                return RiskViolation(
                    code="MAX_POSITION_NOTIONAL_EXCEEDED",
                    message="Projected absolute position notional exceeds the maximum.",
                    observed_value=observed_notional,
                    limit_value=self.max_notional,
                    scope=context.scope,
                )
        return None
