"""HandleExecutionReport application use case."""

from pytradekit.execution import ExecutionReport, ExecutionStatus
from pytradekit.orders.application.models import OrderSnapshot
from pytradekit.orders.application.process_fill import ProcessFill
from pytradekit.orders.domain import InvalidOrderError, OrderNotFoundError
from pytradekit.orders.ports import OrderRepository, PortfolioEffectPort
from pytradekit.portfolio.domain import AccountId


class HandleExecutionReport:
    """Apply canonical external execution facts without transport-order regression."""

    def __init__(
        self,
        *,
        repository: OrderRepository,
        portfolio_effects: PortfolioEffectPort | None = None,
    ) -> None:
        self._repository = repository
        self._process_fill = ProcessFill(
            repository=repository,
            portfolio_effects=portfolio_effects,
        )

    def execute(
        self,
        report: ExecutionReport,
        *,
        account_id: AccountId | None = None,
    ) -> OrderSnapshot:
        """Apply one execution report to the referenced order."""
        if report.status in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}:
            fill = report.fill
            if fill is None:
                raise InvalidOrderError("Fill execution report requires a Fill.")
            return self._process_fill.execute(
                fill,
                external_order_id=report.external_order_id,
                account_id=account_id,
            )

        order = self._repository.get(report.order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {report.order_id} was not found.")

        if report.status is ExecutionStatus.ACCEPTED:
            external_order_id = report.external_order_id
            if external_order_id is None:
                raise InvalidOrderError("Accepted execution report requires external_order_id.")
            order.accept(
                external_order_id=external_order_id,
                occurred_at=report.occurred_at,
            )
        elif report.status is ExecutionStatus.REJECTED:
            reason = report.rejection_reason
            if reason is None:
                raise InvalidOrderError("Rejected execution report requires a reason.")
            order.reject(reason=reason, occurred_at=report.occurred_at)
        elif report.status is ExecutionStatus.CANCELLED:
            order.confirm_cancel(occurred_at=report.occurred_at)
        elif report.status is ExecutionStatus.EXPIRED:
            order.expire(occurred_at=report.occurred_at)

        self._repository.save(order)
        return OrderSnapshot.from_order(order)
