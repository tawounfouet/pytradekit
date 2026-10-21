"""Backtesting domain public surface."""

from pytradekit.backtesting.domain.backtest_run import BacktestRun, BacktestRunStatus
from pytradekit.backtesting.domain.backtest_run_id import BacktestRunId
from pytradekit.backtesting.domain.cost_model import (
    BpsFeeModel,
    CostModel,
    FillContext,
    FixedFeeModel,
    ZeroCostModel,
)
from pytradekit.backtesting.domain.execution_model import ExecutionModel, SimpleBarExecutionModel
from pytradekit.backtesting.domain.latency_model import FixedEventLatency, LatencyModel, ZeroLatency
from pytradekit.backtesting.domain.metrics import (
    BacktestMetrics,
    EquityPoint,
    calculate_max_drawdown,
)
from pytradekit.backtesting.domain.report import BacktestReport
from pytradekit.backtesting.domain.run_manifest import RunManifest, deterministic_config_hash
from pytradekit.backtesting.domain.slippage_model import (
    FixedBpsSlippage,
    SlippageModel,
    ZeroSlippage,
)

__all__ = [
    "BacktestMetrics",
    "BacktestReport",
    "BacktestRun",
    "BacktestRunId",
    "BacktestRunStatus",
    "BpsFeeModel",
    "CostModel",
    "EquityPoint",
    "ExecutionModel",
    "FillContext",
    "FixedBpsSlippage",
    "FixedEventLatency",
    "FixedFeeModel",
    "LatencyModel",
    "RunManifest",
    "SimpleBarExecutionModel",
    "SlippageModel",
    "ZeroCostModel",
    "ZeroLatency",
    "ZeroSlippage",
    "calculate_max_drawdown",
    "deterministic_config_hash",
]
