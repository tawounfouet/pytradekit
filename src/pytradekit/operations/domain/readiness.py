"""Operational readiness distinct from liveness and trading readiness."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pytradekit.shared import DomainValidationError, require_utc_datetime


class LivenessStatus(StrEnum):
    """Whether the process itself is alive enough to continue serving probes."""

    PROCESS_LIVE = "PROCESS_LIVE"
    NOT_LIVE = "NOT_LIVE"


@dataclass(frozen=True, slots=True)
class OperationalReadinessReport:
    """Aggregate operational state without redefining trading readiness."""

    liveness: LivenessStatus
    operational_ready: bool
    trading_ready: bool
    reasons: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.liveness, LivenessStatus):
            raise DomainValidationError("OperationalReadinessReport liveness is invalid.")
        if type(self.operational_ready) is not bool:
            raise DomainValidationError("operational_ready must be a bool.")
        if type(self.trading_ready) is not bool:
            raise DomainValidationError("trading_ready must be a bool.")
        require_utc_datetime(
            self.observed_at,
            field_name="OperationalReadinessReport observed_at",
        )
