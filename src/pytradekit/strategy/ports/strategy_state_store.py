"""Strategy state storage port."""

from typing import Protocol

from pytradekit.strategy.domain import StrategyRunId, StrategyState


class StrategyStateStore(Protocol):
    """Storage boundary for explicit versioned strategy state."""

    def load(self, run_id: StrategyRunId) -> StrategyState:
        ...

    def save(self, run_id: StrategyRunId, state: StrategyState) -> None:
        ...
