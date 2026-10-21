"""Deterministic backtest metrics."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pytradekit.shared import Money, require_utc_datetime


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Portfolio valuation recorded after one processed market event."""

    timestamp: datetime
    nav: Money
    gross_exposure: Money
    net_exposure: Money

    def __post_init__(self) -> None:
        require_utc_datetime(self.timestamp, field_name="EquityPoint timestamp")


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Small P0 analytics surface for milestone 0.4."""

    total_return: Decimal
    absolute_pnl: Money
    max_drawdown: Decimal
    number_of_orders: int
    number_of_fills: int
    risk_rejections: int


def calculate_max_drawdown(points: tuple[EquityPoint, ...]) -> Decimal:
    if not points:
        return Decimal("0")
    peak = points[0].nav.amount
    maximum = Decimal("0")
    for point in points:
        value = point.nav.amount
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (peak - value) / peak
            if drawdown > maximum:
                maximum = drawdown
    return maximum
