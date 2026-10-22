"""PostgreSQL repositories for Security."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pytradekit.security.adapters.postgres.models import (
    SecurityActorModel,
    SecurityRoleAssignmentModel,
    SecurityRoleModel,
    SecurityRolePermissionModel,
)
from pytradekit.security.domain import (
    AccountScopeKind,
    Actor,
    ActorId,
    ActorType,
    AuthorizationEnvironment,
    AuthorizationScope,
    OperationScopeKind,
    Permission,
    PermissionSet,
    Role,
    RoleAssignment,
    RoleId,
)
from pytradekit.shared import require_utc_datetime


class PostgresActorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, actor: Actor) -> None:
        row = self._session.get(SecurityActorModel, actor.id.value)
        if row is None:
            self._session.add(SecurityActorModel(
                id=actor.id.value,
                actor_type=actor.type.value,
                display_name=actor.display_name,
                enabled=actor.enabled,
            ))
        else:
            row.actor_type = actor.type.value
            row.display_name = actor.display_name
            row.enabled = actor.enabled
        self._session.flush()

    def get(self, actor_id: ActorId) -> Actor | None:
        row = self._session.get(SecurityActorModel, actor_id.value)
        if row is None:
            return None
        return Actor(
            ActorId(row.id),
            ActorType(row.actor_type),
            row.display_name,
            row.enabled,
        )


class PostgresRoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, role: Role) -> None:
        row = self._session.get(SecurityRoleModel, role.id.value)
        if row is None:
            self._session.add(SecurityRoleModel(id=role.id.value, name=role.name))
        else:
            row.name = role.name
        self._session.execute(delete(SecurityRolePermissionModel).where(
            SecurityRolePermissionModel.role_id == role.id.value
        ))
        for permission in sorted(role.permissions, key=lambda item: item.value):
            self._session.add(SecurityRolePermissionModel(
                role_id=role.id.value,
                permission=permission.value,
            ))
        self._session.flush()

    def get(self, role_id: RoleId) -> Role | None:
        row = self._session.get(SecurityRoleModel, role_id.value)
        if row is None:
            return None
        statement = select(SecurityRolePermissionModel.permission).where(
            SecurityRolePermissionModel.role_id == role_id.value
        ).order_by(SecurityRolePermissionModel.permission)
        permission_values = self._session.execute(statement).scalars().all()
        permissions = frozenset(
            Permission(value)
            for value in permission_values
        )
        return Role(RoleId(row.id), row.name, PermissionSet(permissions))


class PostgresRoleAssignmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, assignment: RoleAssignment) -> None:
        self._session.add(SecurityRoleAssignmentModel(
            id=uuid4(),
            actor_id=assignment.actor_id.value,
            role_id=assignment.role_id.value,
            environment=assignment.scope.environment.value,
            account_scope=assignment.scope.account_scope.value,
            account_id=assignment.scope.account_id,
            operation_scope=assignment.scope.operation_scope.value,
            operation=(
                assignment.scope.operation.value
                if assignment.scope.operation is not None
                else None
            ),
            valid_from=assignment.valid_from,
            valid_until=assignment.valid_until,
            assigned_by=assignment.assigned_by.value,
            created_at=assignment.created_at,
        ))
        self._session.flush()

    def list_for_actor(self, actor_id: ActorId) -> tuple[RoleAssignment, ...]:
        statement = select(SecurityRoleAssignmentModel).where(
            SecurityRoleAssignmentModel.actor_id == actor_id.value
        ).order_by(
            SecurityRoleAssignmentModel.valid_from,
            SecurityRoleAssignmentModel.role_id,
        )
        rows = self._session.execute(statement).scalars().all()
        return tuple(self._from_model(row) for row in rows)

    def revoke(
        self,
        *,
        actor_id: ActorId,
        role_id: RoleId,
        scope: AuthorizationScope,
        revoked_at: datetime,
    ) -> int:
        timestamp = require_utc_datetime(revoked_at, field_name="RoleAssignment revoked_at")
        statement = select(SecurityRoleAssignmentModel).where(
            SecurityRoleAssignmentModel.actor_id == actor_id.value,
            SecurityRoleAssignmentModel.role_id == role_id.value,
            SecurityRoleAssignmentModel.environment == scope.environment.value,
            SecurityRoleAssignmentModel.account_scope == scope.account_scope.value,
            SecurityRoleAssignmentModel.account_id == scope.account_id,
            SecurityRoleAssignmentModel.operation_scope == scope.operation_scope.value,
            SecurityRoleAssignmentModel.operation == (
                scope.operation.value if scope.operation is not None else None
            ),
            SecurityRoleAssignmentModel.valid_from <= timestamp,
        )
        count = 0
        for row in self._session.execute(statement).scalars().all():
            if row.valid_until is None or timestamp < row.valid_until:
                row.valid_until = timestamp
                count += 1
        self._session.flush()
        return count

    @staticmethod
    def _from_model(row: SecurityRoleAssignmentModel) -> RoleAssignment:
        scope = AuthorizationScope(
            environment=AuthorizationEnvironment(row.environment),
            account_scope=AccountScopeKind(row.account_scope),
            operation_scope=OperationScopeKind(row.operation_scope),
            account_id=row.account_id,
            operation=Permission(row.operation) if row.operation is not None else None,
        )
        return RoleAssignment(
            actor_id=ActorId(row.actor_id),
            role_id=RoleId(row.role_id),
            scope=scope,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            assigned_by=ActorId(row.assigned_by),
            created_at=row.created_at,
        )
