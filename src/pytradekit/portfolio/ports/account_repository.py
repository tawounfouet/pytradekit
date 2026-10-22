"""Account repository port."""

from typing import Protocol

from pytradekit.portfolio.domain import Account, AccountId


class AccountRepository(Protocol):
    """Persistence boundary for canonical economic accounts."""

    def get(self, account_id: AccountId) -> Account | None:
        """Return one account by canonical identity."""
        ...

    def save(self, account: Account) -> None:
        """Persist one account."""
        ...

    def list_all(self) -> tuple[Account, ...]:
        """Return all known accounts in stable identity order."""
        ...
