"""In-memory PortfolioViewPort implementation."""

from copy import deepcopy

from pytradekit.portfolio.domain import AccountId, PortfolioSnapshot


class InMemoryPortfolioView:
    """Deterministic snapshot view used by risk qualification."""

    def __init__(self) -> None:
        self._snapshots: dict[AccountId, PortfolioSnapshot] = {}

    def set_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        self._snapshots[snapshot.account_id] = deepcopy(snapshot)

    def get_snapshot(self, account_id: AccountId) -> PortfolioSnapshot | None:
        snapshot = self._snapshots.get(account_id)
        return deepcopy(snapshot) if snapshot is not None else None
