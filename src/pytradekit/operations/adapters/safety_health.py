"""Decorate SafetyEvidence with critical operational health."""

from dataclasses import replace

from pytradekit.operations.domain import HealthComponent
from pytradekit.operations.services import HealthRegistry
from pytradekit.portfolio.domain import AccountId
from pytradekit.runtime.ports import ClockPort
from pytradekit.safety.domain import SafetyEvidence
from pytradekit.safety.ports import SafetyEvidenceProvider

_DEFAULT_CRITICAL = frozenset(
    {
        HealthComponent.DATABASE,
        HealthComponent.BROKER_COMMAND,
        HealthComponent.RUNTIME,
    }
)


class HealthAwareSafetyEvidenceProvider:
    """Project operational health into safety without owning economic truth."""

    def __init__(
        self,
        *,
        delegate: SafetyEvidenceProvider,
        health: HealthRegistry,
        clock: ClockPort,
        critical_components: frozenset[HealthComponent] = _DEFAULT_CRITICAL,
    ) -> None:
        self._delegate = delegate
        self._health = health
        self._clock = clock
        self._critical_components = critical_components

    def get(self, account_id: AccountId) -> SafetyEvidence | None:
        evidence = self._delegate.get(account_id)
        if evidence is None:
            return None
        critical_healthy = self._health.critical_healthy(
            components=self._critical_components,
            at=self._clock.now(),
        )
        return replace(
            evidence,
            critical_health_healthy=critical_healthy,
        )
