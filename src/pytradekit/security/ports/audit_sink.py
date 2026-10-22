"""Authorization audit boundary."""

from typing import Protocol

from pytradekit.security.domain import AuthorizationDecision


class AuthorizationAuditSink(Protocol):
    """Record one sensitive authorization decision."""

    def record(self, decision: AuthorizationDecision) -> None:
        ...
