"""Persistence and audit ports for safety governance."""

from datetime import datetime
from typing import Protocol

from pytradekit.safety.domain.audit import SafetyAuditEvent
from pytradekit.safety.domain.dangerous_action import (
    DangerousActionConfirmation,
)
from pytradekit.safety.domain.ids import (
    DangerousActionConfirmationId,
    KillSwitchId,
    RiskOverrideId,
)
from pytradekit.safety.domain.kill_switch import KillSwitch
from pytradekit.safety.domain.risk_override import RiskOverride


class KillSwitchRepository(Protocol):
    def get(self, switch_id: KillSwitchId) -> KillSwitch | None:
        ...

    def list_active(self) -> tuple[KillSwitch, ...]:
        ...

    def save(
        self,
        switch: KillSwitch,
        *,
        expected_version: int | None,
    ) -> None:
        ...


class RiskOverrideRepository(Protocol):
    def get(self, override_id: RiskOverrideId) -> RiskOverride | None:
        ...

    def list_active(self, *, at: datetime) -> tuple[RiskOverride, ...]:
        ...

    def save(
        self,
        override: RiskOverride,
        *,
        expected_version: int | None,
    ) -> None:
        ...


class DangerousActionConfirmationRepository(Protocol):
    def get(
        self,
        confirmation_id: DangerousActionConfirmationId,
    ) -> DangerousActionConfirmation | None:
        ...

    def save(self, confirmation: DangerousActionConfirmation) -> None:
        ...


class SafetyAuditSink(Protocol):
    def record(self, event: SafetyAuditEvent) -> None:
        ...
