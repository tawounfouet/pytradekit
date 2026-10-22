"""Authorization policy and service tests."""

from datetime import UTC, datetime, timedelta

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


def _service(
    *,
    permissions: PermissionSet,
    scope: AuthorizationScope,
    enabled: bool = True,
    valid_until: datetime | None = None,
) -> tuple[AuthorizationService, ActorId]:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = InMemoryActorRepository()
    roles = InMemoryRoleRepository()
    assignments = InMemoryRoleAssignmentRepository()
    actors.save(Actor(actor_id, ActorType.HUMAN, "actor", enabled))
    actors.save(Actor(admin_id, ActorType.HUMAN, "admin"))
    roles.save(Role(role_id, "role", permissions))
    assignments.add(RoleAssignment(
        actor_id=actor_id,
        role_id=role_id,
        scope=scope,
        valid_from=NOW - timedelta(minutes=1),
        valid_until=valid_until,
        assigned_by=admin_id,
        created_at=NOW - timedelta(minutes=1),
    ))
    return AuthorizationService(
        actors=actors,
        roles=roles,
        assignments=assignments,
        clock=FakeClock.at(NOW),
    ), actor_id


def test_permission_missing_denies() -> None:
    service, actor_id = _service(
        permissions=PermissionSet.of(Permission.VIEW_ORDERS),
        scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
    )
    decision = service.authorize(
        actor_id=actor_id,
        permission=Permission.SUBMIT_ORDER,
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id="account-1",
            operation=Permission.SUBMIT_ORDER,
        ),
    )
    assert not decision.allowed
    assert decision.reason_code is AuthorizationReason.PERMISSION_MISSING


def test_scope_mismatch_denies() -> None:
    service, actor_id = _service(
        permissions=PermissionSet.of(Permission.SUBMIT_ORDER),
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id="account-a",
        ),
    )
    decision = service.authorize(
        actor_id=actor_id,
        permission=Permission.SUBMIT_ORDER,
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id="account-b",
            operation=Permission.SUBMIT_ORDER,
        ),
    )
    assert decision.reason_code is AuthorizationReason.SCOPE_MISMATCH


def test_disabled_actor_denies() -> None:
    service, actor_id = _service(
        permissions=PermissionSet.of(Permission.SUBMIT_ORDER),
        scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
        enabled=False,
    )
    decision = service.authorize(
        actor_id=actor_id,
        permission=Permission.SUBMIT_ORDER,
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id="account-1",
            operation=Permission.SUBMIT_ORDER,
        ),
    )
    assert decision.reason_code is AuthorizationReason.ACTOR_DISABLED


def test_expired_assignment_denies() -> None:
    service, actor_id = _service(
        permissions=PermissionSet.of(Permission.SUBMIT_ORDER),
        scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
        valid_until=NOW - timedelta(seconds=1),
    )
    decision = service.authorize(
        actor_id=actor_id,
        permission=Permission.SUBMIT_ORDER,
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id="account-1",
            operation=Permission.SUBMIT_ORDER,
        ),
    )
    assert decision.reason_code is AuthorizationReason.ASSIGNMENT_EXPIRED


def test_matching_permission_and_scope_allows() -> None:
    service, actor_id = _service(
        permissions=PermissionSet.of(Permission.SUBMIT_ORDER),
        scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
    )
    decision = service.authorize(
        actor_id=actor_id,
        permission=Permission.SUBMIT_ORDER,
        scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id="account-1",
            operation=Permission.SUBMIT_ORDER,
        ),
    )
    assert decision.allowed
    assert decision.reason_code is AuthorizationReason.ALLOWED
