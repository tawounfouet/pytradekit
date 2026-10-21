"""Consumer-owned execution port used by the Orders application layer."""

from typing import Protocol

from pytradekit.execution import CancelResult, ExecutionReport, SubmissionResult
from pytradekit.orders.domain import Order


class ExecutionPort(Protocol):
    """Broker-neutral order execution boundary."""

    def submit(self, order: Order) -> SubmissionResult:
        """Submit an order and return the immediate known result."""
        ...

    def cancel(self, order: Order) -> CancelResult:
        """Request cancellation and return the immediate known result."""
        ...

    def query_order(self, order: Order) -> ExecutionReport | None:
        """Query the execution venue for the latest known order fact."""
        ...
