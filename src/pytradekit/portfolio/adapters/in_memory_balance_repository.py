"""In-memory BalanceRepository implementation."""

from copy import deepcopy

from pytradekit.portfolio.domain import AccountId, Balance
from pytradekit.shared import Currency


class InMemoryBalanceRepository:
    """Deterministic in-memory balance store."""

    def __init__(self) -> None:
        self._balances: dict[tuple[AccountId, Currency], Balance] = {}

    def get(self, account_id: AccountId, currency: Currency) -> Balance | None:
        balance = self._balances.get((account_id, currency))
        return deepcopy(balance) if balance is not None else None

    def save(self, balance: Balance) -> None:
        self._balances[(balance.account_id, balance.currency)] = deepcopy(balance)

    def list_for_account(self, account_id: AccountId) -> tuple[Balance, ...]:
        balances = [
            deepcopy(balance)
            for (stored_account_id, _), balance in self._balances.items()
            if stored_account_id == account_id
        ]
        return tuple(sorted(balances, key=lambda item: item.currency.code))
