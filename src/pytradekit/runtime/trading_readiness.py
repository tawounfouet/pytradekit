"""Trading readiness after provider reconciliation and stream startup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pytradekit.runtime.readiness import ReadinessCheck, ReadinessCheckStatus


class TradingReadinessState(StrEnum):
    """Aggregate runtime state after full startup reconciliation."""

    TRADING_READY = "TRADING_READY"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True, slots=True)
class TradingReadinessReport:
    """Sanitized readiness result for the fully assembled trading runtime."""

    provider: str
    environment: str
    account: str
    checks: tuple[ReadinessCheck, ...]
    gaps: tuple[str, ...] = ()

    @property
    def state(self) -> TradingReadinessState:
        """Return TRADING_READY only when every gate passes and no gap remains."""

        checks_pass = all(
            check.status is ReadinessCheckStatus.PASS for check in self.checks
        )
        if checks_pass and not self.gaps:
            return TradingReadinessState.TRADING_READY
        return TradingReadinessState.NOT_READY

    @property
    def trading_ready(self) -> bool:
        """Return whether the runtime may admit new economic commands."""

        return self.state is TradingReadinessState.TRADING_READY

    def to_dict(self) -> dict[str, object]:
        """Return a sanitized diagnostic representation."""

        return {
            "provider": self.provider,
            "environment": self.environment,
            "account": self.account,
            "state": self.state.value,
            "trading_ready": self.trading_ready,
            "checks": [check.to_dict() for check in self.checks],
            "gaps": list(self.gaps),
        }
