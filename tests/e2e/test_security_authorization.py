"""End-to-end authorization qualification before provider calls."""

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
from pytradekit.orders.application import (
    CancelOrder,
    CancelOrderCommand,
    SubmitOrder,
    SubmitOrderCommand,
)
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
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock

NOW = datetime(2026, 10, 22, 20, 0, tzinfo=UTC)


class CountingExecutionPort:
    def __init__(self) -> None:
        self.submit_calls = 0
        self.cancel_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=f"external-{order.id}",
        )

    def cancel(self, order: Order) -> CancelResult:
        self.cancel_calls += 1
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        return None


def _gate(
    *,
    permissions: PermissionSet,
    assignment_scope: AuthorizationScope,
    account_id: AccountId,
    enabled: bool = True,
    valid_until: datetime | None = None,
) -> tuple[OrdersAuthorizationGate, InMemoryAuthorizationAuditSink]:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = InMemoryActorRepository()
    roles = InMemoryRoleRepository()
    assignments = InMemoryRoleAssignmentRepository()
    actors.save(Actor(actor_id, ActorType.HUMAN, "principal", enabled))
    actors.save(Actor(admin_id, ActorType.HUMAN, "admin"))
    roles.save(Role(role_id, "role", permissions))
    assignments.add(RoleAssignment(
        actor_id=actor_id,
        role_id=role_id,
        scope=assignment_scope,
        valid_from=NOW - timedelta(minutes=1),
        valid_until=valid_until,
        assigned_by=admin_id,
        created_at=NOW - timedelta(minutes=1),
    ))
    principal = AuthenticatedPrincipal(
        actor_id=actor_id,
        authentication_method="test",
        authenticated_at=NOW,
        session_reference=f"session-{account_id}",
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
    return OrdersAuthorizationGate(
        authorize_action=action,
        environment=AuthorizationEnvironment.PAPER,
    ), audit


def _command(*, account_id: AccountId, order_id: OrderId) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        account_id=account_id,
        order_id=order_id,
    )


def test_viewer_cannot_submit_and_provider_is_not_called() -> None:
    account_id = AccountId.new()
    gate, audit = _gate(
        permissions=PermissionSet.of(Permission.VIEW_ORDERS),
        assignment_scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
        account_id=account_id,
    )
    repository = InMemoryOrderRepository()
    execution = CountingExecutionPort()
    order_id = OrderId.new()
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=gate,
    )
    with pytest.raises(AuthorizationDeniedError, match="PERMISSION_MISSING"):
        submit.execute(_command(account_id=account_id, order_id=order_id))
    assert execution.submit_calls == 0
    assert repository.get(order_id) is None
    assert audit.decisions[-1].reason_code is AuthorizationReason.PERMISSION_MISSING


def test_account_scope_mismatch_cannot_reach_provider() -> None:
    assigned_account = AccountId.new()
    requested_account = AccountId.new()
    gate, audit = _gate(
        permissions=PermissionSet.of(Permission.SUBMIT_ORDER),
        assignment_scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id=str(assigned_account),
        ),
        account_id=requested_account,
    )
    execution = CountingExecutionPort()
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=gate,
    )
    with pytest.raises(AuthorizationDeniedError, match="SCOPE_MISMATCH"):
        submit.execute(_command(account_id=requested_account, order_id=OrderId.new()))
    assert execution.submit_calls == 0
    assert audit.decisions[-1].reason_code is AuthorizationReason.SCOPE_MISMATCH


def test_trader_can_submit_inside_scope() -> None:
    account_id = AccountId.new()
    gate, audit = _gate(
        permissions=PermissionSet.of(Permission.SUBMIT_ORDER),
        assignment_scope=AuthorizationScope.for_account(
            environment=AuthorizationEnvironment.PAPER,
            account_id=str(account_id),
        ),
        account_id=account_id,
    )
    execution = CountingExecutionPort()
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=gate,
    )
    result = submit.execute(_command(account_id=account_id, order_id=OrderId.new()))
    assert result.submission_status is SubmissionStatus.ACKNOWLEDGED
    assert execution.submit_calls == 1
    assert audit.decisions[-1].reason_code is AuthorizationReason.ALLOWED


def test_viewer_cannot_cancel_and_provider_is_not_called() -> None:
    account_id = AccountId.new()
    repository = InMemoryOrderRepository()
    execution = CountingExecutionPort()
    unrestricted = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
    )
    submitted = unrestricted.execute(_command(
        account_id=account_id,
        order_id=OrderId.new(),
    ))
    gate, audit = _gate(
        permissions=PermissionSet.of(Permission.VIEW_ORDERS),
        assignment_scope=AuthorizationScope.all_accounts(
            environment=AuthorizationEnvironment.PAPER
        ),
        account_id=account_id,
    )
    cancel = CancelOrder(
        repository=repository,
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=gate,
    )
    original_cancel_calls = execution.cancel_calls
    with pytest.raises(AuthorizationDeniedError, match="PERMISSION_MISSING"):
        cancel.execute(CancelOrderCommand(
            order_id=submitted.order.order_id,
            account_id=account_id,
        ))
    assert execution.cancel_calls == original_cancel_calls
    assert audit.decisions[-1].reason_code is AuthorizationReason.PERMISSION_MISSING
