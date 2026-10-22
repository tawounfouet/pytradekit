"""Governed RiskOverride request, approval, creation, and revocation."""

from datetime import datetime

from pytradekit.portfolio.domain import AccountId
from pytradekit.runtime.ports import ClockPort
from pytradekit.safety.application._scope import risk_override_authorization_scope
from pytradekit.safety.application.confirmation import (
    ValidateDangerousActionConfirmation,
)
from pytradekit.safety.domain import (
    DangerousAction,
    DangerousActionConfirmationId,
    RiskOverride,
    RiskOverrideId,
    RiskOverrideScope,
    SafetyAction,
    SafetyAuditEvent,
)
from pytradekit.safety.domain.errors import SafetyGovernanceError
from pytradekit.safety.ports import (
    KillSwitchRepository,
    RiskOverrideRepository,
    SafetyAuditSink,
    SafetyEvidenceProvider,
)
from pytradekit.safety.services import SafetyGate
from pytradekit.security.application import AuthorizeAction
from pytradekit.security.domain import AuthorizationEnvironment, Permission
from pytradekit.security.ports import PrincipalProvider
from pytradekit.shared import CorrelationId


class RequestRiskOverride:
    """Create a PENDING, explicitly expiring risk exception request."""

    def __init__(
        self,
        *,
        authorize: AuthorizeAction,
        principal_provider: PrincipalProvider,
        repository: RiskOverrideRepository,
        audit: SafetyAuditSink,
        clock: ClockPort,
        environment: AuthorizationEnvironment,
    ) -> None:
        self._authorize = authorize
        self._principal_provider = principal_provider
        self._repository = repository
        self._audit = audit
        self._clock = clock
        self._environment = environment

    def execute(
        self,
        *,
        scope: RiskOverrideScope,
        reason: str,
        valid_from: datetime,
        valid_until: datetime,
        correlation_id: CorrelationId,
    ) -> RiskOverride:
        auth_scope = risk_override_authorization_scope(
            environment=self._environment,
            permission=Permission.CREATE_RISK_OVERRIDE,
            override_scope=scope,
        )
        self._authorize.ensure_allowed(
            permission=Permission.CREATE_RISK_OVERRIDE,
            scope=auth_scope,
        )
        principal = self._principal_provider.current_principal()
        override = RiskOverride(
            id=RiskOverrideId.new(),
            scope=scope,
            reason=reason,
            requested_by=principal.actor_id,
            created_at=self._clock.now(),
            valid_from=valid_from,
            valid_until=valid_until,
            correlation_id=correlation_id,
        )
        self._repository.save(override, expected_version=None)
        self._audit.record(
            SafetyAuditEvent(
                event_type="RISK_OVERRIDE_REQUESTED",
                actor_id=principal.actor_id,
                action=SafetyAction.CREATE_RISK_OVERRIDE.value,
                scope_reference=f"risk-override:{override.id}",
                reason=reason,
                occurred_at=self._clock.now(),
                correlation_id=correlation_id,
            )
        )
        return override


class ApproveRiskOverride:
    """Activate a pending override only when hard safety is already sound."""

    def __init__(
        self,
        *,
        authorize: AuthorizeAction,
        principal_provider: PrincipalProvider,
        confirmations: ValidateDangerousActionConfirmation,
        repository: RiskOverrideRepository,
        kill_switches: KillSwitchRepository,
        evidence: SafetyEvidenceProvider,
        gate: SafetyGate,
        audit: SafetyAuditSink,
        clock: ClockPort,
        environment: AuthorizationEnvironment,
    ) -> None:
        self._authorize = authorize
        self._principal_provider = principal_provider
        self._confirmations = confirmations
        self._repository = repository
        self._kill_switches = kill_switches
        self._evidence = evidence
        self._gate = gate
        self._audit = audit
        self._clock = clock
        self._environment = environment

    def execute(
        self,
        *,
        override_id: RiskOverrideId,
        confirmation_id: DangerousActionConfirmationId,
    ) -> RiskOverride:
        override = self._repository.get(override_id)
        if override is None:
            raise SafetyGovernanceError("RiskOverride was not found.")

        auth_scope = risk_override_authorization_scope(
            environment=self._environment,
            permission=Permission.CREATE_RISK_OVERRIDE,
            override_scope=override.scope,
        )
        self._authorize.ensure_allowed(
            permission=Permission.CREATE_RISK_OVERRIDE,
            scope=auth_scope,
        )
        principal = self._principal_provider.current_principal()
        scope_reference = f"risk-override:{override.id}"
        self._confirmations.consume(
            confirmation_id=confirmation_id,
            actor_id=principal.actor_id,
            action=DangerousAction.CREATE_RISK_OVERRIDE,
            scope_reference=scope_reference,
        )

        account_id = AccountId.parse(override.scope.account_id)
        evidence = self._evidence.get(account_id)
        if evidence is None:
            raise SafetyGovernanceError(
                "RiskOverride approval requires current safety evidence."
            )
        kill_switch_active = any(
            switch.matches(
                environment=self._environment.value,
                account_id=override.scope.account_id,
                strategy_id=override.scope.strategy_id,
            )
            for switch in self._kill_switches.list_active()
        )
        decision = self._gate.evaluate(
            action=SafetyAction.CREATE_RISK_OVERRIDE,
            evidence=evidence,
            kill_switch_active=kill_switch_active,
        )
        if not decision.allowed:
            raise SafetyGovernanceError(
                "RiskOverride cannot bypass current hard safety."
            )

        approved = override.approve(
            actor_id=principal.actor_id,
            occurred_at=self._clock.now(),
        )
        self._repository.save(approved, expected_version=override.version)
        self._audit.record(
            SafetyAuditEvent(
                event_type="RISK_OVERRIDE_APPROVED",
                actor_id=principal.actor_id,
                action=SafetyAction.CREATE_RISK_OVERRIDE.value,
                scope_reference=scope_reference,
                reason=override.reason,
                occurred_at=self._clock.now(),
                correlation_id=override.correlation_id,
            )
        )
        return approved


class CreateRiskOverride:
    """Single-operator convenience flow preserving request and approval semantics."""

    def __init__(
        self,
        *,
        request: RequestRiskOverride,
        approve: ApproveRiskOverride,
    ) -> None:
        self._request = request
        self._approve = approve

    def execute(
        self,
        *,
        scope: RiskOverrideScope,
        reason: str,
        valid_from: datetime,
        valid_until: datetime,
        correlation_id: CorrelationId,
        confirmation_id: DangerousActionConfirmationId,
    ) -> RiskOverride:
        requested = self._request.execute(
            scope=scope,
            reason=reason,
            valid_from=valid_from,
            valid_until=valid_until,
            correlation_id=correlation_id,
        )
        return self._approve.execute(
            override_id=requested.id,
            confirmation_id=confirmation_id,
        )


class RevokeRiskOverride:
    """Revoke an override through authorization plus dangerous confirmation."""

    def __init__(
        self,
        *,
        authorize: AuthorizeAction,
        principal_provider: PrincipalProvider,
        confirmations: ValidateDangerousActionConfirmation,
        repository: RiskOverrideRepository,
        audit: SafetyAuditSink,
        clock: ClockPort,
        environment: AuthorizationEnvironment,
    ) -> None:
        self._authorize = authorize
        self._principal_provider = principal_provider
        self._confirmations = confirmations
        self._repository = repository
        self._audit = audit
        self._clock = clock
        self._environment = environment

    def execute(
        self,
        *,
        override_id: RiskOverrideId,
        confirmation_id: DangerousActionConfirmationId,
    ) -> RiskOverride:
        override = self._repository.get(override_id)
        if override is None:
            raise SafetyGovernanceError("RiskOverride was not found.")
        auth_scope = risk_override_authorization_scope(
            environment=self._environment,
            permission=Permission.REVOKE_RISK_OVERRIDE,
            override_scope=override.scope,
        )
        self._authorize.ensure_allowed(
            permission=Permission.REVOKE_RISK_OVERRIDE,
            scope=auth_scope,
        )
        principal = self._principal_provider.current_principal()
        scope_reference = f"risk-override:{override.id}"
        self._confirmations.consume(
            confirmation_id=confirmation_id,
            actor_id=principal.actor_id,
            action=DangerousAction.REVOKE_RISK_OVERRIDE,
            scope_reference=scope_reference,
        )
        revoked = override.revoke(
            actor_id=principal.actor_id,
            occurred_at=self._clock.now(),
        )
        self._repository.save(revoked, expected_version=override.version)
        self._audit.record(
            SafetyAuditEvent(
                event_type="RISK_OVERRIDE_REVOKED",
                actor_id=principal.actor_id,
                action=SafetyAction.REVOKE_RISK_OVERRIDE.value,
                scope_reference=scope_reference,
                reason=override.reason,
                occurred_at=self._clock.now(),
                correlation_id=override.correlation_id,
            )
        )
        return revoked
