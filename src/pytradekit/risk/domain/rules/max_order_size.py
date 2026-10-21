"""Maximum order size rule."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.risk.domain import RiskContext, RiskDecision, RiskViolation
from pytradekit.shared import DomainValidationError, Money


@dataclass(frozen=True, slots=True)
class MaxOrderSize:
    """Reject orders whose projected notional or quantity exceeds the limit."""

    max_notional: Money
    max_quantity: Decimal | None = None

    @property
    def decision(self) -> RiskDecision:
        return RiskDecision.REJECT

    def __post_init__(self) -> None:
        if self.max_notional.amount <= 0:
            raise DomainValidationError("MaxOrderSize max_notional must be positive.")
        if self.max_quantity is not None:
            if not self.max_quantity.is_finite() or self.max_quantity <= 0:
                raise DomainValidationError("MaxOrderSize max_quantity must be positive.")

    def evaluate(self, context: RiskContext) -> RiskViolation | None:
        observed = context.projected.order_notional
        if observed.currency != self.max_notional.currency:
            return RiskViolation(
                code="ORDER_CURRENCY_MISMATCH",
                message="Order notional currency does not match the configured limit.",
                observed_value=observed,
                limit_value=self.max_notional,
                scope=context.scope,
            )
        if observed > self.max_notional:
            return RiskViolation(
                code="MAX_ORDER_SIZE_EXCEEDED",
                message="Projected order notional exceeds the configured maximum.",
                observed_value=observed,
                limit_value=self.max_notional,
                scope=context.scope,
            )
        if self.max_quantity is not None and context.order.quantity.value > self.max_quantity:
            return RiskViolation(
                code="MAX_ORDER_QUANTITY_EXCEEDED",
                message="Order quantity exceeds the configured maximum.",
                observed_value=context.order.quantity.value,
                limit_value=self.max_quantity,
                scope=context.scope,
            )
        return None
