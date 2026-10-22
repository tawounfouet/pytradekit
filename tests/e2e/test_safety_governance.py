"""End-to-end qualification for LOT-04 safety governance."""

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
from pytradekit.orders.ports import (
    OrderSafetyDeniedError,
    RiskGateResult,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety import (
    DangerousAction,
    DangerousActionConfirmationId,
    KillSwitch,
    KillSwitchId,
    KillSwitchScope,
    KillSwitchState,
    RiskOverride,
    RiskOverrideId,
    RiskOverrideScope,
    SafetyEvidence,
    SafetyGate,
)
from pytradekit.safety.adapters import (
    InMemoryDangerousActionConfirmationRepository,
    InMemoryKillSwitchRepository,
    InMemoryRiskOverrideRepository,
    InMemorySafetyAuditSink,
    InMemorySafetyEvidenceProvider,
    OrdersSafetyGate,
)
from pytradekit.safety.application import (
    ConfirmDangerousAction,
    CreateRiskOverride,
    ReleaseKillSwitch,
    RevokeRiskOverride,
    ValidateDangerousActionConfirmation,
)
from pytradekit.security import (
    Actor,
    ActorId,
    ActorType,
    AuthenticatedPrincipal,
    AuthorizationEnvironment,
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
from pytradekit.security.application import AuthorizeAction
from pytradekit.security.domain.errors import AuthorizationDeniedError
from pytradekit.security.services import AuthorizationService
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
)
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


class CountingExecutionPort:
    def __init__(self) -> None:
        self.submit_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=f"external-{order.id}",
        )

    def cancel(self, order: Order) -> CancelResult:
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        return None


class RejectingRiskPort:
    """Risk port that exposes a reliable projected risk increase."""

    def evaluate(
        self,
        order: Order,
        *,
        account_id: AccountId,
        reference_price: Price | None,
        strategy_id: str | None,
        start_of_day_nav: Money | None,
    ) -> RiskGateResult:
        del order, account_id, reference_price, strategy_id, start_of_day_nav
        return RiskGateResult(
            allowed=False,
            decision="reject",
            violation_codes=("MAX_ORDER_SIZE_EXCEEDED",),
            risk_increasing=True,
        )


def _safe_evidence() -> SafetyEvidence:
    return SafetyEvidence(
        consistency_status=ConsistencyStatus.CONSISTENT,
        state_confidence=StateConfidence.HIGH,
        recovery_state=RecoveryState.IDLE,
        runtime_lifecycle=RuntimeLifecycleState.READY,
        trading_ready=True,
    )


def _command(
    *,
    account_id: AccountId,
    instrument_id: InstrumentId,
) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        account_id=account_id,
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        reference_price=Price(Decimal("100"), Currency("USD")),
    )


def _authorization(
    *,
    account_id: AccountId,
    permissions: PermissionSet,
) -> tuple[AuthorizeAction, StaticPrincipalProvider]:
    actor_id = ActorId.new()
    admin_id = ActorId.new()
    role_id = RoleId.new()
    actors = InMemoryActorRepository()
    roles = InMemoryRoleRepository()
    assignments = InMemoryRoleAssignmentRepository()
    actors.save(Actor(actor_id, ActorType.HUMAN, "risk-manager"))
    actors.save(Actor(admin_id, ActorType.HUMAN, "admin"))
    roles.save(Role(role_id, "role", permissions))
    assignments.add(
        RoleAssignment(
            actor_id=actor_id,
            role_id=role_id,
            scope=AuthorizationScope.for_account(
                environment=AuthorizationEnvironment.PAPER,
                account_id=str(account_id),
            ),
            valid_from=NOW - timedelta(minutes=1),
            assigned_by=admin_id,
            created_at=NOW - timedelta(minutes=1),
        )
    )
    principal = StaticPrincipalProvider(
        AuthenticatedPrincipal(
            actor_id=actor_id,
            authentication_method="test",
            authenticated_at=NOW,
        )
    )
    authorize = AuthorizeAction(
        principal_provider=principal,
        authorization=AuthorizationService(
            actors=actors,
            roles=roles,
            assignments=assignments,
            clock=FakeClock.at(NOW),
        ),
        audit_sink=InMemoryAuthorizationAuditSink(),
    )
    return authorize, principal


def test_kill_switch_blocks_provider_even_with_matching_override() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    actor_id = ActorId.new()
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(account_id, _safe_evidence())

    kill_switches = InMemoryKillSwitchRepository()
    kill_switches.save(
        KillSwitch(
            id=KillSwitchId.new(),
            state=KillSwitchState.ACTIVE,
            scope=KillSwitchScope.ACCOUNT,
            environment="PAPER",
            scope_id=str(account_id),
            reason="incident",
            activated_by=actor_id,
            activated_at=NOW,
        ),
        expected_version=None,
    )

    overrides = InMemoryRiskOverrideRepository()
    override = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(
            account_id=str(account_id),
            risk_rule="MAX_ORDER_SIZE_EXCEEDED",
            instrument_id=str(instrument_id),
        ),
        reason="temporary",
        requested_by=actor_id,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=5),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor_id, occurred_at=NOW)
    overrides.save(override, expected_version=None)

    safety = OrdersSafetyGate(
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        evidence=evidence,
        kill_switches=kill_switches,
        risk_overrides=overrides,
    )
    execution = CountingExecutionPort()
    repository = InMemoryOrderRepository()
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=FakeClock.at(NOW),
        risk=RejectingRiskPort(),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=safety,
    )

    with pytest.raises(OrderSafetyDeniedError):
        submit.execute(
            _command(account_id=account_id, instrument_id=instrument_id)
        )

    assert execution.submit_calls == 0


def test_safe_override_can_bypass_risk_policy_only() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    actor_id = ActorId.new()
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(account_id, _safe_evidence())
    overrides = InMemoryRiskOverrideRepository()
    override = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(
            account_id=str(account_id),
            risk_rule="MAX_ORDER_SIZE_EXCEEDED",
            instrument_id=str(instrument_id),
        ),
        reason="temporary",
        requested_by=actor_id,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=5),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor_id, occurred_at=NOW)
    overrides.save(override, expected_version=None)

    safety = OrdersSafetyGate(
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        evidence=evidence,
        risk_overrides=overrides,
    )
    execution = CountingExecutionPort()
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=FakeClock.at(NOW),
        risk=RejectingRiskPort(),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=safety,
    )

    result = submit.execute(
        _command(account_id=account_id, instrument_id=instrument_id)
    )

    assert result.submission_status is SubmissionStatus.ACKNOWLEDGED
    assert result.risk_decision == "reject"
    assert result.risk_override_applied
    assert execution.submit_calls == 1


def test_unauthorized_kill_switch_release_is_denied() -> None:
    account_id = AccountId.new()
    authorize, principal = _authorization(
        account_id=account_id,
        permissions=PermissionSet.of(Permission.VIEW_RUNTIME),
    )
    repository = InMemoryKillSwitchRepository()
    switch = KillSwitch(
        id=KillSwitchId.new(),
        state=KillSwitchState.ACTIVE,
        scope=KillSwitchScope.ACCOUNT,
        environment="PAPER",
        scope_id=str(account_id),
        reason="incident",
        activated_by=principal.current_principal().actor_id,
        activated_at=NOW,
    )
    repository.save(switch, expected_version=None)
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(account_id, _safe_evidence())
    confirmations = InMemoryDangerousActionConfirmationRepository()
    validator = ValidateDangerousActionConfirmation(
        repository=confirmations,
        clock=FakeClock.at(NOW),
        process_nonce="process-a",
    )
    release = ReleaseKillSwitch(
        authorize=authorize,
        principal_provider=principal,
        confirmations=validator,
        repository=repository,
        evidence=evidence,
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        audit=InMemorySafetyAuditSink(),
        clock=FakeClock.at(NOW),
        environment=AuthorizationEnvironment.PAPER,
    )

    with pytest.raises(AuthorizationDeniedError):
        release.execute(
            switch_id=switch.id,
            evidence_account_id=account_id,
            release_reason="recovered",
            confirmation_id=DangerousActionConfirmationId.new(),
        )

    assert repository.get(switch.id) == switch


def test_release_create_and_revoke_are_confirmed_and_audited() -> None:
    account_id = AccountId.new()
    permissions = PermissionSet.of(
        Permission.RELEASE_KILL_SWITCH,
        Permission.CREATE_RISK_OVERRIDE,
        Permission.REVOKE_RISK_OVERRIDE,
    )
    authorize, principal = _authorization(
        account_id=account_id,
        permissions=permissions,
    )
    audit = InMemorySafetyAuditSink()
    confirmations = InMemoryDangerousActionConfirmationRepository()
    confirmer = ConfirmDangerousAction(
        principal_provider=principal,
        repository=confirmations,
        audit=audit,
        clock=FakeClock.at(NOW),
        process_nonce="process-a",
    )
    validator = ValidateDangerousActionConfirmation(
        repository=confirmations,
        clock=FakeClock.at(NOW),
        process_nonce="process-a",
    )
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(account_id, _safe_evidence())
    kill_switches = InMemoryKillSwitchRepository()
    switch = KillSwitch(
        id=KillSwitchId.new(),
        state=KillSwitchState.ACTIVE,
        scope=KillSwitchScope.ACCOUNT,
        environment="PAPER",
        scope_id=str(account_id),
        reason="incident",
        activated_by=principal.current_principal().actor_id,
        activated_at=NOW,
    )
    kill_switches.save(switch, expected_version=None)

    release_confirmation = confirmer.execute(
        action=DangerousAction.RELEASE_KILL_SWITCH,
        scope_reference=f"kill-switch:{switch.id}",
        challenge_reference="release-confirm",
    )
    released = ReleaseKillSwitch(
        authorize=authorize,
        principal_provider=principal,
        confirmations=validator,
        repository=kill_switches,
        evidence=evidence,
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        audit=audit,
        clock=FakeClock.at(NOW),
        environment=AuthorizationEnvironment.PAPER,
    ).execute(
        switch_id=switch.id,
        evidence_account_id=account_id,
        release_reason="recovered",
        confirmation_id=release_confirmation.id,
    )
    assert not released.active

    overrides = InMemoryRiskOverrideRepository()
    create_confirmation = confirmer.execute(
        action=DangerousAction.CREATE_RISK_OVERRIDE,
        scope_reference=f"risk-override-create:{account_id}",
        challenge_reference="override-create",
    )
    create = CreateRiskOverride(
        authorize=authorize,
        principal_provider=principal,
        confirmations=validator,
        repository=overrides,
        kill_switches=kill_switches,
        evidence=evidence,
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        audit=audit,
        clock=FakeClock.at(NOW),
        environment=AuthorizationEnvironment.PAPER,
    )
    override = create.execute(
        scope=RiskOverrideScope(account_id=str(account_id)),
        reason="temporary",
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=5),
        correlation_id=CorrelationId.new(),
        confirmation_id=create_confirmation.id,
    )
    assert override.is_active(NOW)

    revoke_confirmation = confirmer.execute(
        action=DangerousAction.REVOKE_RISK_OVERRIDE,
        scope_reference=f"risk-override:{override.id}",
        challenge_reference="override-revoke",
    )
    revoked = RevokeRiskOverride(
        authorize=authorize,
        principal_provider=principal,
        confirmations=validator,
        repository=overrides,
        audit=audit,
        clock=FakeClock.at(NOW),
        environment=AuthorizationEnvironment.PAPER,
    ).execute(
        override_id=override.id,
        confirmation_id=revoke_confirmation.id,
    )

    assert not revoked.is_active(NOW)
    event_types = {event.event_type for event in audit.events}
    assert "KILL_SWITCH_RELEASED" in event_types
    assert "RISK_OVERRIDE_CREATED" in event_types
    assert "RISK_OVERRIDE_REVOKED" in event_types
    assert "DANGEROUS_ACTION_CONFIRMED" in event_types
