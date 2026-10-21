"""Versioned risk policy."""

from dataclasses import dataclass

from pytradekit.risk.domain.risk_limit import RiskLimit
from pytradekit.risk.domain.risk_policy_id import RiskPolicyId
from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Immutable collection of risk limits at one scope."""

    id: RiskPolicyId
    name: str
    scope: RiskScope
    limits: tuple[RiskLimit, ...]
    enabled: bool
    version: int
    scope_id: str | None = None
    allow_reduce_only_when_halted: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, RiskPolicyId):
            raise DomainValidationError("RiskPolicy id must be a RiskPolicyId.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainValidationError("RiskPolicy name must be a non-empty string.")
        if not isinstance(self.scope, RiskScope):
            raise DomainValidationError("RiskPolicy scope must be a RiskScope.")
        if type(self.version) is not int or self.version < 1:
            raise DomainValidationError("RiskPolicy version must be a positive integer.")
        if self.scope is RiskScope.GLOBAL and self.scope_id is not None:
            raise DomainValidationError("GLOBAL RiskPolicy must not define scope_id.")
        if self.scope is not RiskScope.GLOBAL and (
            self.scope_id is None or not self.scope_id.strip()
        ):
            raise DomainValidationError(
                "Non-global RiskPolicy requires a non-empty scope_id."
            )
