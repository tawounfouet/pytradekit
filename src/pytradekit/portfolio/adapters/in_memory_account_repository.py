"""In-memory AccountRepository implementation."""

from copy import deepcopy

from pytradekit.portfolio.domain import Account, AccountId


class InMemoryAccountRepository:
    """Deterministic in-memory account store."""

    def __init__(self) -> None:
        self._accounts: dict[AccountId, Account] = {}

    def get(self, account_id: AccountId) -> Account | None:
        account = self._accounts.get(account_id)
        return deepcopy(account) if account is not None else None

    def save(self, account: Account) -> None:
        self._accounts[account.id] = deepcopy(account)

    def list_all(self) -> tuple[Account, ...]:
        accounts = sorted(self._accounts.values(), key=lambda item: str(item.id))
        return tuple(deepcopy(account) for account in accounts)
