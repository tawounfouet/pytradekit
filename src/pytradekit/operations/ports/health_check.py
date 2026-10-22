"""Health check dependency boundary."""

from typing import Protocol

from pytradekit.operations.domain import HealthComponent, HealthReport


class HealthCheckPort(Protocol):
    """Observe one dependency without mutating it."""

    @property
    def component(self) -> HealthComponent:
        ...

    def check(self) -> HealthReport:
        ...
