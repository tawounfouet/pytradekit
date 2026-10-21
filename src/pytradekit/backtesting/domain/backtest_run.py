"""Backtest run lifecycle."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pytradekit.backtesting.domain.backtest_run_id import BacktestRunId
from pytradekit.backtesting.domain.metrics import BacktestMetrics
from pytradekit.backtesting.domain.run_manifest import RunManifest
from pytradekit.shared import DomainValidationError, require_utc_datetime
from pytradekit.strategy.domain import StrategyRunId


class BacktestRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class BacktestRun:
    """Lifecycle record for one deterministic historical run."""

    id: BacktestRunId
    strategy_run_id: StrategyRunId
    manifest: RunManifest
    status: BacktestRunStatus = BacktestRunStatus.CREATED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metrics: BacktestMetrics | None = None

    def start(self, at: datetime) -> None:
        if self.status is not BacktestRunStatus.CREATED:
            raise DomainValidationError("BacktestRun can start only from CREATED.")
        self.started_at = require_utc_datetime(at, field_name="BacktestRun start time")
        self.status = BacktestRunStatus.RUNNING

    def complete(self, at: datetime, metrics: BacktestMetrics) -> None:
        if self.status is not BacktestRunStatus.RUNNING:
            raise DomainValidationError("BacktestRun can complete only from RUNNING.")
        self.completed_at = require_utc_datetime(at, field_name="BacktestRun completion time")
        self.metrics = metrics
        self.status = BacktestRunStatus.COMPLETED

    def fail(self, at: datetime) -> None:
        self.completed_at = require_utc_datetime(at, field_name="BacktestRun failure time")
        self.status = BacktestRunStatus.FAILED
