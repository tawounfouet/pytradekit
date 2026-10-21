"""Portfolio cash balance."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.shared import Currency, DomainValidationError, Money, require_utc_datetime


@dataclass(frozen=True, slots=True)
class Balance:
    """Internal accounting balance for one account and currency."""

    account_id: AccountId
    currency: Currency
    cash: Money
    available: Money | None = None
    reserved: Money | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, AccountId):
            raise DomainValidationError("Balance account_id must be an AccountId.")
        if not isinstance(self.currency, Currency):
            raise DomainValidationError("Balance currency must be a Currency.")
        if not isinstance(self.cash, Money) or self.cash.currency != self.currency:
            raise DomainValidationError("Balance cash must use the balance currency.")
        for field_name, value in (("available", self.available), ("reserved", self.reserved)):
            if value is not None:
                if not isinstance(value, Money) or value.currency != self.currency:
                    raise DomainValidationError(
                        f"Balance {field_name} must use the balance currency."
                    )
        if self.reserved is not None and self.reserved.amount < Decimal("0"):
            raise DomainValidationError("Balance reserved amount must not be negative.")
        if self.updated_at is not None:
            require_utc_datetime(self.updated_at, field_name="Balance updated_at")

    def with_cash(self, cash: Money, *, updated_at: datetime) -> Balance:
        require_utc_datetime(updated_at, field_name="Balance updated_at")
        return replace(self, cash=cash, updated_at=updated_at)

    def debit(self, amount: Money, *, updated_at: datetime) -> Balance:
        return self.with_cash(self.cash - amount, updated_at=updated_at)

    def credit(self, amount: Money, *, updated_at: datetime) -> Balance:
        return self.with_cash(self.cash + amount, updated_at=updated_at)
