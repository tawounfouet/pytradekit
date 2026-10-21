"""Strategy definition and runtime protocol."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pytradekit.market_data.domain import MarketDataEvent, TimerEvent
from pytradekit.portfolio.domain import PortfolioSnapshot
from pytradekit.shared import DomainValidationError, require_utc_datetime
from pytradekit.strategy.domain.requirements import StrategyRequirements
from pytradekit.strategy.domain.signal import Signal
from pytradekit.strategy.domain.strategy_id import StrategyId
from pytradekit.strategy.domain.strategy_run_id import StrategyRunId
from pytradekit.strategy.domain.strategy_state import StrategyState
from pytradekit.strategy.domain.strategy_version import StrategyVersion
from pytradekit.strategy.domain.target_position import TargetPosition


@dataclass(frozen=True, slots=True)
class Strategy:
    """Immutable strategy definition independent from one concrete run."""

    id: StrategyId
    name: str
    version: StrategyVersion
    requirements: StrategyRequirements

    def __post_init__(self) -> None:
        if not isinstance(self.id, StrategyId):
            raise DomainValidationError("Strategy id must be a StrategyId.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainValidationError("Strategy name must be a non-empty string.")
        if not isinstance(self.version, StrategyVersion):
            raise DomainValidationError("Strategy version must be a StrategyVersion.")
        if not isinstance(self.requirements, StrategyRequirements):
            raise DomainValidationError("Strategy requirements must be StrategyRequirements.")


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Only the information a strategy is allowed to observe at one event."""

    run_id: StrategyRunId
    current_time: datetime
    portfolio: PortfolioSnapshot
    state: StrategyState
    trading_enabled: bool

    def __post_init__(self) -> None:
        require_utc_datetime(self.current_time, field_name="StrategyContext current_time")


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """Explicit result of one strategy callback."""

    state: StrategyState
    signals: tuple[Signal, ...] = ()
    targets: tuple[TargetPosition, ...] = ()


class StrategyProtocol(Protocol):
    """Minimal callback contract implemented by strategy code."""

    def on_market_data(
        self,
        event: MarketDataEvent,
        context: StrategyContext,
    ) -> StrategyDecision:
        """Handle one already-emitted market data event."""
        ...

    def on_timer(
        self,
        event: TimerEvent,
        context: StrategyContext,
    ) -> StrategyDecision:
        """Handle one deterministic timer event."""
        ...
