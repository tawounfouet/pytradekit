"""Strategy run aggregate."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import DomainValidationError, require_utc_datetime
from pytradekit.strategy.domain.strategy_id import StrategyId
from pytradekit.strategy.domain.strategy_run_id import StrategyRunId
from pytradekit.strategy.domain.strategy_run_status import StrategyRunStatus
from pytradekit.strategy.domain.strategy_version import StrategyVersion


@dataclass(slots=True)
class StrategyRun:
    """Lifecycle state for one concrete strategy execution."""

    id: StrategyRunId
    strategy_id: StrategyId
    strategy_version: StrategyVersion
    status: StrategyRunStatus = StrategyRunStatus.CREATED
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    state_version: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.id, StrategyRunId):
            raise DomainValidationError("StrategyRun id must be a StrategyRunId.")
        if not isinstance(self.strategy_id, StrategyId):
            raise DomainValidationError("StrategyRun strategy_id must be a StrategyId.")
        if not isinstance(self.strategy_version, StrategyVersion):
            raise DomainValidationError("StrategyRun strategy_version must be a StrategyVersion.")
        if not isinstance(self.status, StrategyRunStatus):
            raise DomainValidationError("StrategyRun status must be a StrategyRunStatus.")
        if type(self.state_version) is not int or self.state_version < 0:
            raise DomainValidationError("StrategyRun state_version must be non-negative.")
        if self.started_at is not None:
            require_utc_datetime(self.started_at, field_name="StrategyRun started_at")
        if self.stopped_at is not None:
            require_utc_datetime(self.stopped_at, field_name="StrategyRun stopped_at")

    def start(self, *, at: datetime) -> None:
        self._require(StrategyRunStatus.CREATED, "start")
        timestamp = require_utc_datetime(at, field_name="StrategyRun start time")
        self.status = StrategyRunStatus.STARTING
        self.started_at = timestamp
        self.status = StrategyRunStatus.RUNNING

    def pause(self) -> None:
        self._require(StrategyRunStatus.RUNNING, "pause")
        self.status = StrategyRunStatus.PAUSED

    def resume(self) -> None:
        self._require(StrategyRunStatus.PAUSED, "resume")
        self.status = StrategyRunStatus.RUNNING

    def stop(self, *, at: datetime) -> None:
        self._require(StrategyRunStatus.RUNNING, "stop")
        timestamp = require_utc_datetime(at, field_name="StrategyRun stop time")
        self.status = StrategyRunStatus.STOPPING
        self.stopped_at = timestamp
        self.status = StrategyRunStatus.STOPPED

    def fail(self, *, at: datetime) -> None:
        if self.status in {StrategyRunStatus.STOPPED, StrategyRunStatus.CANCELLED}:
            raise DomainValidationError(f"Cannot fail StrategyRun from {self.status.value}.")
        self.stopped_at = require_utc_datetime(at, field_name="StrategyRun failure time")
        self.status = StrategyRunStatus.FAILED

    def record_state_version(self, version: int) -> None:
        if type(version) is not int or version < self.state_version:
            raise DomainValidationError("StrategyRun state version cannot move backwards.")
        self.state_version = version

    def _require(self, expected: StrategyRunStatus, operation: str) -> None:
        if self.status is not expected:
            raise DomainValidationError(
                "Cannot "
                f"{operation} StrategyRun from {self.status.value}; "
                f"expected {expected.value}."
            )
