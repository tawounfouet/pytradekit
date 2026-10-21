"""Static order lifecycle classifications."""

from pytradekit.orders.domain.order_status import OrderStatus

TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    }
)

CANCELLABLE_ORDER_STATUSES = frozenset(
    {
        OrderStatus.SUBMITTED,
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED,
    }
)
