"""Repository-backed authorization service."""

from pytradekit.runtime.ports import ClockPort
from pytradekit.security.domain import (
    ActorId,
    AuthorizationDecision,
    AuthorizationReason,
    AuthorizationScope,
    OperationScopeKind,
    Permission,
    Role,
    RoleId,
)
from pytradekit.security.ports import (
    ActorRepository,
    RoleAssignmentRepository,
    RoleRepository,
)
from pytradekit.security.services.authorization_policy import AuthorizationPolicy
from pytradekit.shared import DomainValidationError


class AuthorizationService:
    """Load current security facts and delegate to the pure authorization policy."""

    def __init__(
        self,
        *,
        actors: ActorRepository,
        roles: RoleRepository,
        assignments: RoleAssignmentRepository,
        clock: ClockPort,
        policy: AuthorizationPolicy | None = None,
    ) -> None:
        self._actors = actors
        self._roles = roles
        self._assignments = assignments
        self._clock = clock
        self._policy = policy or AuthorizationPolicy()

    def authorize(
        self,
        *,
        actor_id: ActorId,
        permission: Permission,
        scope: AuthorizationScope,
    ) -> AuthorizationDecision:
        """Evaluate one permission request from fresh repository state."""
        now = self._clock.now()
        if (
            scope.operation_scope is not OperationScopeKind.OPERATION
            or scope.operation is not permission
        ):
            raise DomainValidationError(
                "Requested authorization scope must name the requested permission."
            )

        actor = self._actors.get(actor_id)
        if actor is None:
            return AuthorizationDecision(
                allowed=False,
                actor_id=actor_id,
                permission=permission,
                scope=scope,
                reason_code=AuthorizationReason.ACTOR_NOT_FOUND,
                evaluated_at=now,
            )

        actor_assignments = self._assignments.list_for_actor(actor_id)
        roles: dict[RoleId, Role] = {}
        for assignment in actor_assignments:
            role = self._roles.get(assignment.role_id)
            if role is not None:
                roles[role.id] = role

        return self._policy.evaluate(
            actor=actor,
            assignments=actor_assignments,
            roles=roles,
            permission=permission,
            requested_scope=scope,
            evaluated_at=now,
        )
