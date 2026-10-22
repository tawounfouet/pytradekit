"""Consumer-owned consistency gate for risk-increasing orders."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId


class ConsistencyGatePort(Protocol):
    """Reject new risk when economic state is not sufficiently trusted."""

    def ensure_risk_increase_allowed(self, account_id: AccountId) -> None: ...
