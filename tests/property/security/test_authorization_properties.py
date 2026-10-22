"""Property tests for deterministic authorization."""

from datetime import UTC, datetime, timedelta

from hypothesis import given, strategies as st

from pytradekit.security import (
    Actor,
    ActorId,
    ActorType,
    AuthorizationEnvironment,
    AuthorizationReason,
    AuthorizationScope,
    Permission,
    PermissionSet,
    Role,
    RoleAssignment,
    RoleId,
)
from pytradekit.security.adapters import (
    InMemoryActorRepository,
    InMemoryRoleAssignmentRepository,
    InMemoryRoleRepository,
)
from pytradekit.security.services import AuthorizationService
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 20, 0, tzinfo=UTC)


@given(account_id=st.uuids().map(str))
def test_no_permission_always_denies(account_id: str) -> None:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = InMemoryActorRepository()
    roles = InMemoryRoleRepository()
    assignments = InMemoryRoleAssignmentRepository()
    actors.save(Actor(actor_id, ActorType.HUMAN, "viewer"))
    actors.save(Actor(admin_id, ActorType.HUMAN, "admin"))
    roles.save(Role(role_id, "VIEWER", PermissionSet.of(Permission.VIEW_ORDERS)))
    assignments.add(RoleAssignment(
        actor_id=actor_id,
        role_id=role_id,
        scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
        valid_from=NOW - timedelta(minutes=1),
        assigned_by=admin_id,
        created_at=NOW - timedelta(minutes=1),
    ))
    service = AuthorizationService(
        actors=actors,
        roles=roles,
        assignments=assignments,
        clock=FakeClock.at(NOW),
    )
    decision = service.authorize(
        actor_id=actor_id,
        permission=Permission.SUBMIT_ORDER,
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id=account_id,
            operation=Permission.SUBMIT_ORDER,
        ),
    )
    assert not decision.allowed
    assert decision.reason_code is AuthorizationReason.PERMISSION_MISSING
