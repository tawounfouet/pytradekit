"""Provider-neutral security domain concepts."""

from pytradekit.security.domain.actor import Actor
from pytradekit.security.domain.actor_id import ActorId
from pytradekit.security.domain.actor_type import ActorType
from pytradekit.security.domain.authorization_decision import (
    AuthorizationDecision,
    AuthorizationReason,
)
from pytradekit.security.domain.authorization_scope import (
    AccountScopeKind,
    AuthorizationEnvironment,
    AuthorizationScope,
    OperationScopeKind,
)
from pytradekit.security.domain.permission import Permission
from pytradekit.security.domain.permission_set import PermissionSet
from pytradekit.security.domain.principal import AuthenticatedPrincipal, PrincipalContext
from pytradekit.security.domain.role import Role
from pytradekit.security.domain.role_assignment import RoleAssignment
from pytradekit.security.domain.role_id import RoleId

__all__ = [
    "AccountScopeKind",
    "Actor",
    "ActorId",
    "ActorType",
    "AuthenticatedPrincipal",
    "AuthorizationDecision",
    "AuthorizationEnvironment",
    "AuthorizationReason",
    "AuthorizationScope",
    "OperationScopeKind",
    "Permission",
    "PermissionSet",
    "PrincipalContext",
    "Role",
    "RoleAssignment",
    "RoleId",
]
