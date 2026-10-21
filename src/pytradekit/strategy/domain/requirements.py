"""Strategy environment requirements."""

from dataclasses import dataclass
from datetime import timedelta

from pytradekit.orders.domain import OrderType
from pytradekit.shared import DomainValidationError, InstrumentId


@dataclass(frozen=True, slots=True)
class StrategyRequirements:
    """Capabilities and historical data required before a strategy can run."""

    instruments: tuple[InstrumentId, ...]
    market_data_types: tuple[str, ...] = ("bar",)
    bar_intervals: tuple[str, ...] = ()
    required_order_types: tuple[OrderType, ...] = (OrderType.MARKET,)
    warmup_bars: int = 0
    staleness_tolerance: timedelta | None = None

    def __post_init__(self) -> None:
        if not self.instruments or not all(
            isinstance(item, InstrumentId) for item in self.instruments
        ):
            raise DomainValidationError("StrategyRequirements requires InstrumentId values.")
        if any(not isinstance(item, str) or not item.strip() for item in self.market_data_types):
            raise DomainValidationError(
                "StrategyRequirements market data types must be non-empty strings."
            )
        if any(not isinstance(item, str) or not item.strip() for item in self.bar_intervals):
            raise DomainValidationError(
                "StrategyRequirements bar intervals must be non-empty strings."
            )
        if any(not isinstance(item, OrderType) for item in self.required_order_types):
            raise DomainValidationError(
                "StrategyRequirements order types must be OrderType values."
            )
        if type(self.warmup_bars) is not int or self.warmup_bars < 0:
            raise DomainValidationError("StrategyRequirements warmup_bars must be non-negative.")
        if self.staleness_tolerance is not None and self.staleness_tolerance < timedelta(0):
            raise DomainValidationError(
                "StrategyRequirements staleness_tolerance must be non-negative."
            )
