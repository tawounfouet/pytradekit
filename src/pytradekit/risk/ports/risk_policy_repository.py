"""RiskPolicy repository port."""

from typing import Protocol

from pytradekit.risk.domain import RiskPolicy, RiskScope


class RiskPolicyRepository(Protocol):
    """Persistence boundary for versioned risk policies."""

    def save(self, policy: RiskPolicy) -> None:
        ...

    def get_active(self, scope: RiskScope, scope_id: str | None) -> RiskPolicy | None:
        ...

    def list_active(self) -> tuple[RiskPolicy, ...]:
        ...
