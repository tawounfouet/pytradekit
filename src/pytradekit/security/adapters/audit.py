"""Authorization audit adapters."""

from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.security.domain import AuthorizationDecision


class InMemoryAuthorizationAuditSink:
    """Collect authorization decisions for qualification and tests."""

    def __init__(self) -> None:
        self.decisions: list[AuthorizationDecision] = []

    def record(self, decision: AuthorizationDecision) -> None:
        self.decisions.append(decision)


class RuntimeAuthorizationAuditSink:
    """Emit sanitized authorization evidence through the runtime observer."""

    def __init__(self, observer: RuntimeObserver) -> None:
        self._observer = observer

    def record(self, decision: AuthorizationDecision) -> None:
        self._observer.event(
            "AuthorizationAllowed" if decision.allowed else "AuthorizationDenied",
            actor_id=str(decision.actor_id),
            permission=decision.permission.value,
            environment=decision.scope.environment.value,
            account_scope=decision.scope.account_scope.value,
            operation_scope=decision.scope.operation_scope.value,
            reason_code=decision.reason_code.value,
            allowed=decision.allowed,
        )
