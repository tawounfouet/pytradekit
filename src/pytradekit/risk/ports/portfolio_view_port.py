"""Consumer-owned portfolio view port for Risk."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId, PortfolioSnapshot


class PortfolioViewPort(Protocol):
    """Read boundary exposing current portfolio facts to Risk."""

    def get_snapshot(self, account_id: AccountId) -> PortfolioSnapshot | None:
        ...
