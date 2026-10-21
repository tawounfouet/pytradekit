"""Explicit simulated execution models."""

from dataclasses import dataclass
from typing import Protocol

from pytradekit.market_data.domain import Bar
from pytradekit.orders.domain import Order, OrderSide, OrderType
from pytradekit.shared import Price


class ExecutionModel(Protocol):
    """Decide whether and at what base price an order is fillable."""

    @property
    def name(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    def fill_price(self, order: Order, bar: Bar) -> Price | None:
        ...


@dataclass(frozen=True, slots=True)
class SimpleBarExecutionModel:
    """Conservative full-fill model using only the next eligible bar."""

    name: str = "simple-bar"
    version: str = "1"

    def fill_price(self, order: Order, bar: Bar) -> Price | None:
        if order.instrument_id != bar.instrument_id:
            return None
        if order.order_type is OrderType.MARKET:
            return bar.open
        limit = order.limit_price
        if limit is None:
            return None
        if limit.currency != bar.open.currency:
            return None
        if order.side is OrderSide.BUY and bar.low.value <= limit.value:
            return limit
        if order.side is OrderSide.SELL and bar.high.value >= limit.value:
            return limit
        return None
