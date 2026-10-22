"""Release-blocker qualification for authorization and scope isolation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import SubmitOrder, SubmitOrderCommand
from pytradekit.orders.domain import Order, OrderId, OrderSide, OrderType, TimeInForce
from pytradekit.portfolio.domain import AccountId
from pytradekit.security import (
    Actor,
    ActorId,
    ActorType,
    AuthenticatedPrincipal,
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
    InMemoryAuthorizationAuditSink,
    InMemoryRoleAssignmentRepository,
    InMemoryRoleRepository,
    StaticPrincipalProvider,
)
from pytradekit.security.adapters.orders_authorization import OrdersAuthorizationGate
from pytradekit.security.application import AuthorizeAction
from pytradekit.security.domain.errors import AuthorizationDeniedError
from pytradekit.security.services import AuthorizationService
from pytradekit.shared import CorrelationId, InstrumentId, Quantity
from pytradekit.testing import ExplicitTestOrderSafetyGate, FakeClock

NOW = datetime(2026, 10, 22, 22, 0, tzinfo=UTC)


class _CountingExecutionPort:
    def __init__(self) -> None:
        self.submit_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=f"external-{order.id}",
        )

    def cancel(self, order: Order) -> CancelResult:
        _ = order
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        _ = order
        return None


def _authorization_gate(
    *,
    account_id: AccountId,
    permissions: PermissionSet,
    assignment_scope: AuthorizationScope,
    valid_until: datetime | None = None,
) -> tuple[OrdersAuthorizationGate, InMemoryAuthorizationAuditSink]:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = InMemoryActorRepository()
    roles = InMemoryRoleRepository()
    assignments = InMemoryRoleAssignmentRepository()
    actors.save(Actor(actor_id, ActorType.HUMAN, "qualified-actor"))
    actors.save(Actor(admin_id, ActorType.HUMAN, "qualified-admin"))
    roles.save(Role(role_id, "qualified-role", permissions))
    assignments.add(
        RoleAssignment(
            actor_id=actor_id,
            role_id=role_id,
            scope=assignment_scope,
            valid_from=NOW - timedelta(minutes=5),
            valid_until=valid_until,
            assigned_by=admin_id,
            created_at=NOW - timedelta(minutes=5),
        )
    )
    principal = AuthenticatedPrincipal(
        actor_id=actor_id,
        authentication_method="qualification",
        authenticated_at=NOW,
    )
    audit = InMemoryAuthorizationAuditSink()
    action = AuthorizeAction(
        principal_provider=StaticPrincipalProvider(principal),
        authorization=AuthorizationService(
            actors=actors,
            roles=roles,
            assignments=assignments,
            clock=FakeClock.at(NOW),
        ),
        audit_sink=audit,
    )
    return (
        OrdersAuthorizationGate(
            authorize_action=action,
            environment=AuthorizationEnvironment.PAPER,
        ),
        audit,
    )


def _command(account_id: AccountId) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        account_id=account_id,
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
    )


@pytest.mark.parametrize(
    ("permissions", "assignment_scope_factory", "valid_until", "reason"),
    [
        (
            PermissionSet.of(Permission.VIEW_ORDERS),
            lambda account: AuthorizationScope.for_account(
                environment=AuthorizationEnvironment.PAPER,
                account_id=str(account),
            ),
            None,
            AuthorizationReason.PERMISSION_MISSING,
        ),
        (
            PermissionSet.of(Permission.SUBMIT_ORDER),
            lambda account: AuthorizationScope.for_account(
                environment=AuthorizationEnvironment.PAPER,
                account_id=f"other-{account}",
            ),
            None,
            AuthorizationReason.SCOPE_MISMATCH,
        ),
        (
            PermissionSet.of(Permission.SUBMIT_ORDER),
            lambda account: AuthorizationScope.for_account(
                environment=AuthorizationEnvironment.BACKTEST,
                account_id=str(account),
            ),
            None,
            AuthorizationReason.SCOPE_MISMATCH,
        ),
        (
            PermissionSet.of(Permission.SUBMIT_ORDER),
            lambda account: AuthorizationScope.for_account(
                environment=AuthorizationEnvironment.PAPER,
                account_id=str(account),
            ),
            NOW,
            AuthorizationReason.ASSIGNMENT_EXPIRED,
        ),
    ],
)
def test_authorization_release_blockers_never_reach_provider(
    permissions: PermissionSet,
    assignment_scope_factory: object,
    valid_until: datetime | None,
    reason: AuthorizationReason,
) -> None:
    account_id = AccountId.new()
    scope_factory = assignment_scope_factory
    assert callable(scope_factory)
    assignment_scope = scope_factory(account_id)
    gate, audit = _authorization_gate(
        account_id=account_id,
        permissions=permissions,
        assignment_scope=assignment_scope,
        valid_until=valid_until,
    )
    execution = _CountingExecutionPort()
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=gate,
        safety_gate=ExplicitTestOrderSafetyGate(),
    )

    with pytest.raises(AuthorizationDeniedError):
        submit.execute(_command(account_id))

    assert execution.submit_calls == 0
    assert audit.decisions[-1].reason_code is reason
