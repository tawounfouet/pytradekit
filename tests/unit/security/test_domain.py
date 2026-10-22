"""Unit tests for Security domain foundations."""

from datetime import UTC, datetime, timedelta

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

NOW = datetime(2026, 10, 22, 19, 0, tzinfo=UTC)


def test_actor_role_and_permissions_are_explicit() -> None:
    actor = Actor(ActorId.new(), ActorType.HUMAN, "Trader One")
    role = Role(
        RoleId.new(),
        "TRADER",
        PermissionSet.of(Permission.VIEW_ORDERS, Permission.SUBMIT_ORDER),
    )
    assert actor.enabled
    assert Permission.SUBMIT_ORDER in role.permissions


def test_scope_matching_is_deterministic() -> None:
    assigned = AuthorizationScope.all_accounts(
        environment=AuthorizationEnvironment.PAPER,
        operation=Permission.SUBMIT_ORDER,
    )
    requested = AuthorizationScope.for_account(
        environment=AuthorizationEnvironment.PAPER,
        account_id="account-1",
        operation=Permission.SUBMIT_ORDER,
    )
    wrong = AuthorizationScope.for_account(
        environment=AuthorizationEnvironment.PAPER,
        account_id="account-1",
        operation=Permission.CANCEL_ORDER,
    )
    assert assigned.covers(requested)
    assert not assigned.covers(wrong)


def test_assignment_expiry_is_deterministic() -> None:
    actor_id = ActorId.new()
    assignment = RoleAssignment(
        actor_id=actor_id,
        role_id=RoleId.new(),
        scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=30),
        assigned_by=actor_id,
        created_at=NOW,
    )
    assert assignment.is_active(NOW)
    assert not assignment.is_active(NOW + timedelta(minutes=30))
