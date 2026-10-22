"""Consumer-owned authorization boundary for sensitive Orders actions."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId


class OrderAuthorizationGatePort(Protocol):
    """Authorize submission and cancellation before economic side effects."""

    def ensure_submit_allowed(self, account_id: AccountId) -> None:
        ...

    def ensure_cancel_allowed(self, account_id: AccountId) -> None:
        ...
