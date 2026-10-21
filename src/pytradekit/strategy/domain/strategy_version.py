"""Logical strategy version."""

from dataclasses import dataclass

from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class StrategyVersion:
    """Validated logical version of strategy code or configuration."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise DomainValidationError("StrategyVersion value must be a non-empty string.")
        object.__setattr__(self, "value", self.value.strip())

    def __str__(self) -> str:
        return self.value
