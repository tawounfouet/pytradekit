"""Authorize one sensitive application action and retain audit evidence."""

from pytradekit.security.domain import (
    AuthorizationDecision,
    AuthorizationScope,
    Permission,
)
from pytradekit.security.domain.errors import AuthorizationDeniedError
from pytradekit.security.ports.audit_sink import AuthorizationAuditSink
from pytradekit.security.ports.principal_provider import PrincipalProvider
from pytradekit.security.services import AuthorizationService


class AuthorizeAction:
    """Resolve the current principal, authorize, audit, and fail closed on demand."""

    def __init__(
        self,
        *,
        principal_provider: PrincipalProvider,
        authorization: AuthorizationService,
        audit_sink: AuthorizationAuditSink,
    ) -> None:
        self._principal_provider = principal_provider
        self._authorization = authorization
        self._audit_sink = audit_sink

    def execute(
        self,
        *,
        permission: Permission,
        scope: AuthorizationScope,
    ) -> AuthorizationDecision:
        principal = self._principal_provider.current_principal()
        decision = self._authorization.authorize(
            actor_id=principal.actor_id,
            permission=permission,
            scope=scope,
        )
        self._audit_sink.record(decision)
        return decision

    def ensure_allowed(
        self,
        *,
        permission: Permission,
        scope: AuthorizationScope,
    ) -> AuthorizationDecision:
        decision = self.execute(permission=permission, scope=scope)
        if not decision.allowed:
            raise AuthorizationDeniedError(decision.reason_code.value)
        return decision
