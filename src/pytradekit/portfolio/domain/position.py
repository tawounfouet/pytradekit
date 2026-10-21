"""Portfolio position accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.portfolio.domain.errors import PortfolioInvariantError
from pytradekit.portfolio.domain.position_side import PositionSide
from pytradekit.shared import (
    Currency,
    DomainValidationError,
    InstrumentId,
    Money,
    Price,
    Quantity,
    require_utc_datetime,
)


@dataclass(slots=True)
class Position:
    """Mutable accounting position using signed quantity semantics."""

    account_id: AccountId
    instrument_id: InstrumentId
    quantity: Decimal
    average_price: Price | None
    realized_pnl: Money
    opened_at: datetime | None
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, AccountId):
            raise DomainValidationError("Position account_id must be an AccountId.")
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("Position instrument_id must be an InstrumentId.")
        if not isinstance(self.quantity, Decimal) or not self.quantity.is_finite():
            raise DomainValidationError("Position quantity must be a finite Decimal.")
        if not isinstance(self.realized_pnl, Money):
            raise DomainValidationError("Position realized_pnl must be Money.")
        if self.average_price is not None:
            if not isinstance(self.average_price, Price):
                raise DomainValidationError("Position average_price must be Price or None.")
            if self.average_price.currency != self.realized_pnl.currency:
                raise DomainValidationError(
                    "Position average_price and realized_pnl currencies must match."
                )
        require_utc_datetime(self.updated_at, field_name="Position updated_at")
        if self.opened_at is not None:
            require_utc_datetime(self.opened_at, field_name="Position opened_at")
        if self.quantity == 0 and self.average_price is not None:
            raise PortfolioInvariantError("Flat position must not have an average price.")
        if self.quantity != 0 and self.average_price is None:
            raise PortfolioInvariantError("Open position requires an average price.")

    @classmethod
    def flat(
        cls,
        *,
        account_id: AccountId,
        instrument_id: InstrumentId,
        currency: Currency,
        occurred_at: datetime,
    ) -> Position:
        timestamp = require_utc_datetime(occurred_at, field_name="Position creation time")
        return cls(
            account_id=account_id,
            instrument_id=instrument_id,
            quantity=Decimal("0"),
            average_price=None,
            realized_pnl=Money.zero(currency),
            opened_at=None,
            updated_at=timestamp,
        )

    @property
    def side(self) -> PositionSide:
        if self.quantity > 0:
            return PositionSide.LONG
        if self.quantity < 0:
            return PositionSide.SHORT
        return PositionSide.FLAT

    def apply_fill(
        self,
        *,
        side: OrderSide,
        quantity: Quantity,
        price: Price,
        occurred_at: datetime,
    ) -> None:
        if not isinstance(side, OrderSide):
            raise DomainValidationError("Position fill side must be an OrderSide.")
        if not isinstance(quantity, Quantity) or quantity.value <= 0:
            raise DomainValidationError("Position fill quantity must be greater than zero.")
        if not isinstance(price, Price):
            raise DomainValidationError("Position fill price must be a Price.")
        timestamp = require_utc_datetime(occurred_at, field_name="Position fill time")
        if timestamp < self.updated_at:
            raise PortfolioInvariantError("Position fill time cannot move backwards.")
        if price.currency != self.realized_pnl.currency:
            raise PortfolioInvariantError("Position fill currency must match position currency.")

        signed_fill = quantity.value if side is OrderSide.BUY else -quantity.value
        current = self.quantity
        new_quantity = current + signed_fill

        if current == 0:
            self.quantity = new_quantity
            self.average_price = price
            self.opened_at = timestamp
            self.updated_at = timestamp
            return

        current_average = self.average_price
        if current_average is None:
            raise PortfolioInvariantError("Open position requires an average price.")

        same_direction = (current > 0 and signed_fill > 0) or (
            current < 0 and signed_fill < 0
        )
        if same_direction:
            total_abs = abs(new_quantity)
            weighted = (
                (abs(current) * current_average.value)
                + (abs(signed_fill) * price.value)
            ) / total_abs
            self.quantity = new_quantity
            self.average_price = Price(weighted, price.currency)
            self.updated_at = timestamp
            return

        closing_quantity = min(abs(current), abs(signed_fill))
        if current > 0:
            pnl_amount = (price.value - current_average.value) * closing_quantity
        else:
            pnl_amount = (current_average.value - price.value) * closing_quantity

        self.realized_pnl = self.realized_pnl + Money(pnl_amount, self.realized_pnl.currency)
        self.quantity = new_quantity

        if new_quantity == 0:
            self.average_price = None
            self.opened_at = None
        elif (current > 0 and new_quantity > 0) or (current < 0 and new_quantity < 0):
            self.average_price = current_average
        else:
            self.average_price = price
            self.opened_at = timestamp

        self.updated_at = timestamp
