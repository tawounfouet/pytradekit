"""Explicit authorization test doubles for non-security-focused tests."""

from pytradekit.portfolio.domain import AccountId


class ExplicitTestOrderAuthorizationGate:
    """Explicitly allow order actions in tests and historical examples only."""

    def __init__(self) -> None:
        self.submit_checks = 0
        self.cancel_checks = 0

    def ensure_submit_allowed(self, account_id: AccountId) -> None:
        """Record one explicit submit authorization check."""
        _ = account_id
        self.submit_checks += 1

    def ensure_cancel_allowed(self, account_id: AccountId) -> None:
        """Record one explicit cancel authorization check."""
        _ = account_id
        self.cancel_checks += 1
