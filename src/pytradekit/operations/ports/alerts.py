"""Alert state and delivery boundaries."""

from dataclasses import dataclass
from typing import Protocol

from pytradekit.operations.domain import Alert, AlertId


@dataclass(frozen=True, slots=True)
class AlertDeliveryResult:
    """Bounded result of routing one stateful alert."""

    attempted: int
    delivered: int
    failure_types: tuple[str, ...]

    @property
    def failures(self) -> int:
        return len(self.failure_types)


class AlertRepositoryPort(Protocol):
    """Persist alert state independently from delivery sinks."""

    def get(self, alert_id: AlertId) -> Alert | None:
        ...

    def find_unresolved_by_deduplication_key(
        self,
        deduplication_key: str,
    ) -> Alert | None:
        ...

    def list_open(self) -> tuple[Alert, ...]:
        ...

    def save(self, alert: Alert) -> None:
        ...


class AlertSinkPort(Protocol):
    """Deliver one alert to one external or local sink."""

    def deliver(self, alert: Alert) -> None:
        ...


class AlertRouterPort(Protocol):
    """Route one alert to configured sinks without owning alert state."""

    def route(self, alert: Alert) -> AlertDeliveryResult:
        ...
