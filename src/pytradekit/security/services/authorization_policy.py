"""Pure authorization decision policy."""

from collections.abc import Mapping
from datetime import datetime

from pytradekit.security.domain import (
    Actor,
    AuthorizationDecision,
    AuthorizationReason,
    AuthorizationScope,
    Permission,
    Role,
    RoleAssignment,
    RoleId,
)


class AuthorizationPolicy:
    """Evaluate role, permission, scope, actor state, and assignment validity."""

    def evaluate(
        self,
        *,
        actor: Actor,
        assignments: tuple[RoleAssignment, ...],
        roles: Mapping[RoleId, Role],
        permission: Permission,
        requested_scope: AuthorizationScope,
        evaluated_at: datetime,
    ) -> AuthorizationDecision:
        """Return one deterministic decision without side effects."""
        if not actor.enabled:
            return self._deny(
                actor=actor,
                permission=permission,
                scope=requested_scope,
                reason=AuthorizationReason.ACTOR_DISABLED,
                evaluated_at=evaluated_at,
            )

        if not assignments:
            return self._deny(
                actor=actor,
                permission=permission,
                scope=requested_scope,
                reason=AuthorizationReason.ROLE_MISSING,
                evaluated_at=evaluated_at,
            )

        active = tuple(
            assignment
            for assignment in assignments
            if assignment.is_active(evaluated_at)
        )
        if not active:
            reason = (
                AuthorizationReason.ASSIGNMENT_EXPIRED
                if any(
                    assignment.valid_until is not None
                    and evaluated_at >= assignment.valid_until
                    for assignment in assignments
                )
                else AuthorizationReason.ROLE_MISSING
            )
            return self._deny(
                actor=actor,
                permission=permission,
                scope=requested_scope,
                reason=reason,
                evaluated_at=evaluated_at,
            )

        known = tuple(
            (assignment, roles.get(assignment.role_id))
            for assignment in active
        )
        permission_assignments = tuple(
            assignment
            for assignment, role in known
            if role is not None and permission in role.permissions
        )
        if not permission_assignments:
            reason = (
                AuthorizationReason.ROLE_MISSING
                if not any(role is not None for _, role in known)
                else AuthorizationReason.PERMISSION_MISSING
            )
            return self._deny(
                actor=actor,
                permission=permission,
                scope=requested_scope,
                reason=reason,
                evaluated_at=evaluated_at,
            )

        if not any(
            assignment.scope.covers(requested_scope)
            for assignment in permission_assignments
        ):
            return self._deny(
                actor=actor,
                permission=permission,
                scope=requested_scope,
                reason=AuthorizationReason.SCOPE_MISMATCH,
                evaluated_at=evaluated_at,
            )

        return AuthorizationDecision(
            allowed=True,
            actor_id=actor.id,
            permission=permission,
            scope=requested_scope,
            reason_code=AuthorizationReason.ALLOWED,
            evaluated_at=evaluated_at,
        )

    @staticmethod
    def _deny(
        *,
        actor: Actor,
        permission: Permission,
        scope: AuthorizationScope,
        reason: AuthorizationReason,
        evaluated_at: datetime,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            actor_id=actor.id,
            permission=permission,
            scope=scope,
            reason_code=reason,
            evaluated_at=evaluated_at,
        )
