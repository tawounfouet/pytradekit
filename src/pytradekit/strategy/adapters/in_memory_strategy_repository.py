"""In-memory StrategyRepository implementation."""

from copy import deepcopy

from pytradekit.strategy.domain import Strategy, StrategyId


class InMemoryStrategyRepository:
    """Deterministic in-memory strategy metadata store."""

    def __init__(self) -> None:
        self._strategies: dict[StrategyId, Strategy] = {}

    def get(self, strategy_id: StrategyId) -> Strategy | None:
        value = self._strategies.get(strategy_id)
        return deepcopy(value) if value is not None else None

    def save(self, strategy: Strategy) -> None:
        self._strategies[strategy.id] = deepcopy(strategy)
