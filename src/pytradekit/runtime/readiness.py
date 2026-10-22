"""Startup readiness model for runtime bootstrap checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReadinessCheckStatus(StrEnum):
    """Outcome of one startup prerequisite check."""

    PASS = "PASS"
    FAIL = "FAIL"


class StartupReadinessState(StrEnum):
    """Aggregate startup state without claiming trading readiness."""

    READY_FOR_STARTUP = "READY_FOR_STARTUP"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    """One sanitized startup readiness observation."""

    name: str
    status: ReadinessCheckStatus
    detail: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-safe representation."""

        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class StartupReadinessReport:
    """Sanitized report for configuration/bootstrap readiness."""

    provider: str
    environment: str
    account: str
    checks: tuple[ReadinessCheck, ...]

    @property
    def state(self) -> StartupReadinessState:
        """Return the aggregate bootstrap state."""

        if all(check.status is ReadinessCheckStatus.PASS for check in self.checks):
            return StartupReadinessState.READY_FOR_STARTUP
        return StartupReadinessState.NOT_READY

    @property
    def ready_for_startup(self) -> bool:
        """Return whether all bootstrap prerequisites passed."""

        return self.state is StartupReadinessState.READY_FOR_STARTUP

    def to_dict(self) -> dict[str, object]:
        """Return a sanitized JSON-safe representation."""

        return {
            "provider": self.provider,
            "environment": self.environment,
            "account": self.account,
            "state": self.state.value,
            "ready_for_startup": self.ready_for_startup,
            "checks": [check.to_dict() for check in self.checks],
            "trading_ready": False,
            "trading_ready_note": (
                "LOT-05 startup readiness does not include stream and reconciliation gates."
            ),
        }
