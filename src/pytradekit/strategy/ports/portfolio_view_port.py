"""Strategy-facing portfolio read boundary."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId, PortfolioSnapshot


class PortfolioViewPort(Protocol):
    """Read-only current portfolio facts available to strategy runtime."""

    def get_snapshot(self, account_id: AccountId) -> PortfolioSnapshot | None:
        ...
