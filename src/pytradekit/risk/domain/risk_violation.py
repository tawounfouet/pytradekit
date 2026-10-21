"""Risk violation details."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.shared import Money


@dataclass(frozen=True, slots=True)
class RiskViolation:
    """Stable machine-readable violation produced by a pure risk rule."""

    code: str
    message: str
    observed_value: Decimal | Money
    limit_value: Decimal | Money
    scope: RiskScope
