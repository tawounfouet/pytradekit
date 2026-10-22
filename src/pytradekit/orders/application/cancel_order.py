"""CancelOrder application use case."""

from pytradekit.execution import CancelStatus
from pytradekit.orders.application.models import (
    CancelOrderCommand,
    CancelOrderResult,
    OrderSnapshot,
)
from pytradekit.orders.domain import InvalidOrderError, OrderNotFoundError
from pytradekit.orders.ports import (
    ExecutionPort,
    OrderAuthorizationGatePort,
    OrderRepository,
)
from pytradekit.runtime.ports import ClockPort


class CancelOrder:
    """Request cancellation while preserving uncertainty and broker races."""

    def __init__(
        self,
        *,
        repository: OrderRepository,
        execution: ExecutionPort,
        clock: ClockPort,
        authorization_gate: OrderAuthorizationGatePort | None = None,
    ) -> None:
        self._repository = repository
        self._execution = execution
        self._clock = clock
        self._authorization_gate = authorization_gate

    def execute(self, command: CancelOrderCommand) -> CancelOrderResult:
        """Execute one cancellation request without blind retry."""
        if self._authorization_gate is not None:
            account_id = command.account_id
            if account_id is None:
                raise InvalidOrderError(
                    "Authorization-gated cancellation requires account_id."
                )
            self._authorization_gate.ensure_cancel_allowed(account_id)

        order = self._repository.get(command.order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {command.order_id} was not found.")

        order.request_cancel(occurred_at=self._clock.now())
        self._repository.save(order)
        cancellation = self._execution.cancel(order)

        if cancellation.status is CancelStatus.REJECTED:
            reason = cancellation.reason
            if reason is None:
                raise InvalidOrderError("Rejected cancellation requires a reason.")
            order.reject_cancel(reason=reason, occurred_at=self._clock.now())
        elif cancellation.status is CancelStatus.UNCERTAIN:
            order.mark_cancel_uncertain(occurred_at=self._clock.now())

        self._repository.save(order)
        return CancelOrderResult(
            order=OrderSnapshot.from_order(order),
            cancel_status=cancellation.status,
        )
