"""In-memory StrategyStateStore implementation."""

from copy import deepcopy

from pytradekit.strategy.domain import StrategyRunId, StrategyState


class InMemoryStrategyStateStore:
    """Deterministic in-memory state store with explicit state versions."""

    def __init__(self) -> None:
        self._states: dict[StrategyRunId, StrategyState] = {}

    def load(self, run_id: StrategyRunId) -> StrategyState:
        return deepcopy(self._states.get(run_id, StrategyState.empty()))

    def save(self, run_id: StrategyRunId, state: StrategyState) -> None:
        current = self._states.get(run_id)
        if current is not None and state.version < current.version:
            raise ValueError("StrategyState version cannot move backwards.")
        self._states[run_id] = deepcopy(state)
