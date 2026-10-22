"""Security repositories against real PostgreSQL."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from pytradekit.security import (
    Actor,
    ActorId,
    ActorType,
    AuthorizationEnvironment,
    AuthorizationScope,
    Permission,
    PermissionSet,
    Role,
    RoleAssignment,
    RoleId,
)
from pytradekit.security.adapters.postgres import (
    PostgresActorRepository,
    PostgresRoleAssignmentRepository,
    PostgresRoleRepository,
)

NOW = datetime(2026, 10, 22, 19, 0, tzinfo=UTC)


def test_security_round_trip(postgres_session: Session) -> None:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = PostgresActorRepository(postgres_session)
    roles = PostgresRoleRepository(postgres_session)
    assignments = PostgresRoleAssignmentRepository(postgres_session)
    actors.save(Actor(actor_id, ActorType.HUMAN, "trader"))
    actors.save(Actor(admin_id, ActorType.HUMAN, "admin"))
    roles.save(Role(role_id, f"TRADER-{role_id}", PermissionSet.of(Permission.SUBMIT_ORDER)))
    scope = AuthorizationScope.for_account(
        environment=AuthorizationEnvironment.PAPER,
        account_id="paper-account",
    )
    assignments.add(RoleAssignment(
        actor_id=actor_id,
        role_id=role_id,
        scope=scope,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=1),
        assigned_by=admin_id,
        created_at=NOW,
    ))
    assert actors.get(actor_id) == Actor(actor_id, ActorType.HUMAN, "trader")
    loaded_role = roles.get(role_id)
    assert loaded_role is not None
    assert Permission.SUBMIT_ORDER in loaded_role.permissions
    assert assignments.list_for_actor(actor_id)[0].scope == scope


def test_assignment_revocation_is_time_bound(postgres_session: Session) -> None:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = PostgresActorRepository(postgres_session)
    roles = PostgresRoleRepository(postgres_session)
    assignments = PostgresRoleAssignmentRepository(postgres_session)
    actors.save(Actor(actor_id, ActorType.SERVICE, "service"))
    actors.save(Actor(admin_id, ActorType.HUMAN, "admin"))
    roles.save(Role(role_id, f"OPS-{role_id}", PermissionSet.of(Permission.RUN_RECONCILIATION)))
    scope = AuthorizationScope.all_accounts(environment=AuthorizationEnvironment.PAPER)
    assignments.add(RoleAssignment(
        actor_id=actor_id,
        role_id=role_id,
        scope=scope,
        valid_from=NOW,
        assigned_by=admin_id,
        created_at=NOW,
    ))
    assert assignments.revoke(
        actor_id=actor_id,
        role_id=role_id,
        scope=scope,
        revoked_at=NOW + timedelta(minutes=5),
    ) == 1
    loaded = assignments.list_for_actor(actor_id)[0]
    assert loaded.is_active(NOW + timedelta(minutes=4))
    assert not loaded.is_active(NOW + timedelta(minutes=5))
