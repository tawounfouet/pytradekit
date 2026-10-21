"""Explicit deterministic latency models."""

from dataclasses import dataclass
from typing import Protocol

from pytradekit.shared import DomainValidationError


class LatencyModel(Protocol):
    """Describe how many future eligible events must pass before fill evaluation."""

    name: str
    version: str

    @property
    def future_events(self) -> int:
        ...


@dataclass(frozen=True, slots=True)
class ZeroLatency:
    name: str = "zero-latency"
    version: str = "1"

    @property
    def future_events(self) -> int:
        return 1


@dataclass(frozen=True, slots=True)
class FixedEventLatency:
    additional_events: int
    name: str = "fixed-event-latency"
    version: str = "1"

    def __post_init__(self) -> None:
        if type(self.additional_events) is not int or self.additional_events < 0:
            raise DomainValidationError("FixedEventLatency additional_events must be non-negative.")

    @property
    def future_events(self) -> int:
        return 1 + self.additional_events
