"""Balance repository port."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId, Balance
from pytradekit.shared import Currency


class BalanceRepository(Protocol):
    """Persistence boundary for portfolio balances."""

    def get(self, account_id: AccountId, currency: Currency) -> Balance | None:
        ...

    def save(self, balance: Balance) -> None:
        ...

    def list_for_account(self, account_id: AccountId) -> tuple[Balance, ...]:
        ...
