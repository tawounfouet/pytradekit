"""Strategy definition repository port."""

from typing import Protocol

from pytradekit.strategy.domain import Strategy, StrategyId


class StrategyRepository(Protocol):
    """Persistence boundary for immutable strategy metadata."""

    def get(self, strategy_id: StrategyId) -> Strategy | None:
        ...

    def save(self, strategy: Strategy) -> None:
        ...
