"""ProcessFill application use case."""

from pytradekit.execution import Fill
from pytradekit.orders.application.models import OrderSnapshot
from pytradekit.orders.domain import InvalidOrderError, OrderNotFoundError
from pytradekit.orders.ports import OrderRepository, PortfolioEffectPort
from pytradekit.portfolio.domain import AccountId


class ProcessFill:
    """Apply one fill idempotently to Order and optionally Portfolio."""

    def __init__(
        self,
        *,
        repository: OrderRepository,
        portfolio_effects: PortfolioEffectPort | None = None,
    ) -> None:
        self._repository = repository
        self._portfolio_effects = portfolio_effects

    def execute(
        self,
        fill: Fill,
        *,
        external_order_id: str | None = None,
        account_id: AccountId | None = None,
    ) -> OrderSnapshot:
        """Apply one fill exactly once and return the updated order snapshot."""
        order = self._repository.get(fill.order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {fill.order_id} was not found.")
        if self._portfolio_effects is not None and account_id is None:
            raise InvalidOrderError("Portfolio-integrated fill processing requires account_id.")

        applied = order.apply_fill(
            fill_id=fill.deduplication_key,
            fill_quantity=fill.quantity,
            occurred_at=fill.occurred_at,
            external_order_id=external_order_id,
        )
        self._repository.save(order)

        if applied and self._portfolio_effects is not None:
            effective_account_id = account_id
            if effective_account_id is None:
                raise InvalidOrderError(
                    "Portfolio-integrated fill processing requires account_id."
                )
            self._portfolio_effects.apply_fill(
                fill,
                account_id=effective_account_id,
                instrument_id=order.instrument_id,
                side=order.side,
            )

        return OrderSnapshot.from_order(order)
