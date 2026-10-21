"""Canonical economic account."""

from dataclasses import dataclass

from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.shared import Currency, DomainValidationError


@dataclass(frozen=True, slots=True)
class Account:
    """Internal economic account identity independent from broker sessions."""

    id: AccountId
    base_currency: Currency
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, AccountId):
            raise DomainValidationError("Account id must be an AccountId.")
        if not isinstance(self.base_currency, Currency):
            raise DomainValidationError("Account base_currency must be a Currency.")
        if self.name is not None and not self.name.strip():
            raise DomainValidationError("Account name must not be empty.")
