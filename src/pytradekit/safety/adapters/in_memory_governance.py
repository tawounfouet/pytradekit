"""Deterministic in-memory safety governance repositories."""

from copy import deepcopy
from datetime import datetime

from pytradekit.safety.domain import (
    DangerousActionConfirmation,
    DangerousActionConfirmationId,
    KillSwitch,
    KillSwitchId,
    RiskOverride,
    RiskOverrideId,
)
from pytradekit.safety.domain.audit import SafetyAuditEvent
from pytradekit.safety.domain.errors import SafetyConcurrencyError


class InMemoryKillSwitchRepository:
    def __init__(self) -> None:
        self._items: dict[KillSwitchId, KillSwitch] = {}

    def get(self, switch_id: KillSwitchId) -> KillSwitch | None:
        item = self._items.get(switch_id)
        return deepcopy(item) if item is not None else None

    def list_active(self) -> tuple[KillSwitch, ...]:
        items = [deepcopy(item) for item in self._items.values() if item.active]
        return tuple(sorted(items, key=lambda item: str(item.id)))

    def save(
        self,
        switch: KillSwitch,
        *,
        expected_version: int | None,
    ) -> None:
        current = self._items.get(switch.id)
        if current is None:
            if expected_version is not None:
                raise SafetyConcurrencyError("KillSwitch does not yet exist.")
        elif expected_version != current.version:
            raise SafetyConcurrencyError("Stale KillSwitch version.")
        self._items[switch.id] = deepcopy(switch)


class InMemoryRiskOverrideRepository:
    def __init__(self) -> None:
        self._items: dict[RiskOverrideId, RiskOverride] = {}

    def get(self, override_id: RiskOverrideId) -> RiskOverride | None:
        item = self._items.get(override_id)
        return deepcopy(item) if item is not None else None

    def list_active(self, *, at: datetime) -> tuple[RiskOverride, ...]:
        items = [
            deepcopy(item)
            for item in self._items.values()
            if item.is_active(at)
        ]
        return tuple(sorted(items, key=lambda item: str(item.id)))

    def save(
        self,
        override: RiskOverride,
        *,
        expected_version: int | None,
    ) -> None:
        current = self._items.get(override.id)
        if current is None:
            if expected_version is not None:
                raise SafetyConcurrencyError("RiskOverride does not yet exist.")
        elif expected_version != current.version:
            raise SafetyConcurrencyError("Stale RiskOverride version.")
        self._items[override.id] = deepcopy(override)


class InMemoryDangerousActionConfirmationRepository:
    def __init__(self) -> None:
        self._items: dict[
            DangerousActionConfirmationId,
            DangerousActionConfirmation,
        ] = {}

    def get(
        self,
        confirmation_id: DangerousActionConfirmationId,
    ) -> DangerousActionConfirmation | None:
        item = self._items.get(confirmation_id)
        return deepcopy(item) if item is not None else None

    def save(self, confirmation: DangerousActionConfirmation) -> None:
        self._items[confirmation.id] = deepcopy(confirmation)


class InMemorySafetyAuditSink:
    def __init__(self) -> None:
        self.events: list[SafetyAuditEvent] = []

    def record(self, event: SafetyAuditEvent) -> None:
        self.events.append(deepcopy(event))
