"""Desired trading action before canonical Order creation."""

from dataclasses import dataclass

from pytradekit.orders.domain import OrderSide, OrderType, TimeInForce
from pytradekit.shared import DomainValidationError, InstrumentId, Price, Quantity


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Broker-neutral desired action produced by portfolio construction."""

    instrument_id: InstrumentId
    side: OrderSide
    quantity: Quantity
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    limit_price: Price | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("OrderIntent instrument_id must be an InstrumentId.")
        if not isinstance(self.side, OrderSide):
            raise DomainValidationError("OrderIntent side must be an OrderSide.")
        if not isinstance(self.quantity, Quantity) or self.quantity.value <= 0:
            raise DomainValidationError("OrderIntent quantity must be greater than zero.")
        if not isinstance(self.order_type, OrderType):
            raise DomainValidationError("OrderIntent order_type must be an OrderType.")
        if not isinstance(self.time_in_force, TimeInForce):
            raise DomainValidationError("OrderIntent time_in_force must be a TimeInForce.")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise DomainValidationError("LIMIT OrderIntent requires limit_price.")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise DomainValidationError("MARKET OrderIntent must not define limit_price.")
        if self.reason is not None and not self.reason.strip():
            raise DomainValidationError("OrderIntent reason must not be empty.")
