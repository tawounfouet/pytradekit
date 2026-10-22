"""Strategy admission boundary for runtime safety gates."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId


class StrategyAdmissionPort(Protocol):
    """Decide whether a strategy may emit new portfolio targets."""

    def allow_new_targets(self, account_id: AccountId) -> bool: ...
