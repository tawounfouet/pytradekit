"""Immutable backtest report."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.backtesting.domain.backtest_run_id import BacktestRunId
from pytradekit.backtesting.domain.metrics import BacktestMetrics, EquityPoint
from pytradekit.backtesting.domain.run_manifest import RunManifest
from pytradekit.portfolio.domain import PortfolioSnapshot
from pytradekit.shared import Money, require_utc_datetime


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Deterministic semantic result of one backtest run."""

    run_id: BacktestRunId
    manifest: RunManifest
    started_at: datetime
    completed_at: datetime
    initial_nav: Money
    final_snapshot: PortfolioSnapshot
    metrics: BacktestMetrics
    equity_curve: tuple[EquityPoint, ...]
    schema_version: str = "1"

    def __post_init__(self) -> None:
        require_utc_datetime(self.started_at, field_name="BacktestReport started_at")
        require_utc_datetime(self.completed_at, field_name="BacktestReport completed_at")

    @property
    def final_nav(self) -> Money:
        return self.final_snapshot.nav
