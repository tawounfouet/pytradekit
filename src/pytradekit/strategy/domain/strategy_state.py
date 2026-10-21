"""Explicit versioned strategy state."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field

from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class StrategyState:
    """Serializable explicit state owned by one StrategyRun."""

    version: int = 0
    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version < 0:
            raise DomainValidationError("StrategyState version must be a non-negative integer.")
        if not isinstance(self.values, Mapping):
            raise DomainValidationError("StrategyState values must be a mapping.")
        normalized: dict[str, object] = {}
        for key, value in self.values.items():
            if not isinstance(key, str) or not key.strip():
                raise DomainValidationError("StrategyState keys must be non-empty strings.")
            normalized[key.strip()] = deepcopy(value)
        object.__setattr__(self, "values", normalized)

    @classmethod
    def empty(cls) -> StrategyState:
        return cls()

    def evolve(self, values: Mapping[str, object]) -> StrategyState:
        """Return a new state version with fully explicit replacement values."""
        return StrategyState(version=self.version + 1, values=values)
