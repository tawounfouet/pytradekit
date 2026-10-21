"""In-memory RiskPolicyRepository implementation."""

from copy import deepcopy

from pytradekit.risk.domain import RiskPolicy, RiskPolicyId, RiskScope


class InMemoryRiskPolicyRepository:
    """Deterministic in-memory policy store preserving policy versions."""

    def __init__(self) -> None:
        self._policies: dict[RiskPolicyId, RiskPolicy] = {}

    def save(self, policy: RiskPolicy) -> None:
        self._policies[policy.id] = deepcopy(policy)

    def get_active(self, scope: RiskScope, scope_id: str | None) -> RiskPolicy | None:
        candidates = [
            policy
            for policy in self._policies.values()
            if policy.enabled and policy.scope is scope and policy.scope_id == scope_id
        ]
        if not candidates:
            return None
        selected = max(candidates, key=lambda item: item.version)
        return deepcopy(selected)

    def list_active(self) -> tuple[RiskPolicy, ...]:
        active = [deepcopy(policy) for policy in self._policies.values() if policy.enabled]
        return tuple(sorted(active, key=lambda item: (item.scope.value, item.scope_id or "")))
