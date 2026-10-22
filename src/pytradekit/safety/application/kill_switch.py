"""Governed KillSwitch activation and release."""

from pytradekit.portfolio.domain import AccountId
from pytradekit.runtime.ports import ClockPort
from pytradekit.safety.application._scope import kill_switch_authorization_scope
from pytradekit.safety.application.confirmation import (
    ValidateDangerousActionConfirmation,
)
from pytradekit.safety.domain import (
    DangerousAction,
    DangerousActionConfirmationId,
    KillSwitch,
    KillSwitchId,
    KillSwitchScope,
    KillSwitchState,
    SafetyAction,
    SafetyAuditEvent,
)
from pytradekit.safety.domain.errors import KillSwitchReleaseDeniedError
from pytradekit.safety.ports import (
    KillSwitchRepository,
    SafetyAuditSink,
    SafetyEvidenceProvider,
)
from pytradekit.safety.services import SafetyGate
from pytradekit.security.application import AuthorizeAction
from pytradekit.security.domain import AuthorizationEnvironment, Permission
from pytradekit.security.ports import PrincipalProvider
from pytradekit.shared import CorrelationId


class ActivateKillSwitch:
    """Activate emergency containment with no implicit flatten side effect."""

    def __init__(
        self,
        *,
        authorize: AuthorizeAction,
        principal_provider: PrincipalProvider,
        repository: KillSwitchRepository,
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
        scope: KillSwitchScope,
        scope_id: str | None,
        reason: str,
        correlation_id: CorrelationId | None = None,
    ) -> KillSwitch:
        auth_scope = kill_switch_authorization_scope(
            environment=self._environment,
            permission=Permission.ACTIVATE_KILL_SWITCH,
            scope=scope,
            scope_id=scope_id,
        )
        self._authorize.ensure_allowed(
            permission=Permission.ACTIVATE_KILL_SWITCH,
            scope=auth_scope,
        )
        principal = self._principal_provider.current_principal()
        environment = None if scope is KillSwitchScope.GLOBAL else self._environment.value

        for active in self._repository.list_active():
            if (
                active.scope is scope
                and active.environment == environment
                and active.scope_id == scope_id
            ):
                self._audit.record(
                    SafetyAuditEvent(
                        event_type="KILL_SWITCH_ACTIVATION_REPEATED",
                        actor_id=principal.actor_id,
                        action=SafetyAction.ACTIVATE_KILL_SWITCH.value,
                        scope_reference=f"kill-switch:{active.id}",
                        reason=reason,
                        occurred_at=self._clock.now(),
                        correlation_id=correlation_id,
                    )
                )
                return active

        switch = KillSwitch(
            id=KillSwitchId.new(),
            state=KillSwitchState.ACTIVE,
            scope=scope,
            environment=environment,
            scope_id=scope_id,
            reason=reason,
            activated_by=principal.actor_id,
            activated_at=self._clock.now(),
        )
        self._repository.save(switch, expected_version=None)
        self._audit.record(
            SafetyAuditEvent(
                event_type="KILL_SWITCH_ACTIVATED",
                actor_id=principal.actor_id,
                action=SafetyAction.ACTIVATE_KILL_SWITCH.value,
                scope_reference=f"kill-switch:{switch.id}",
                reason=reason,
                occurred_at=switch.activated_at,
                correlation_id=correlation_id,
            )
        )
        return switch


class ReleaseKillSwitch:
    """Release one blocker only after authorization, confirmation, and safe evidence."""

    def __init__(
        self,
        *,
        authorize: AuthorizeAction,
        principal_provider: PrincipalProvider,
        confirmations: ValidateDangerousActionConfirmation,
        repository: KillSwitchRepository,
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
        self._evidence = evidence
        self._gate = gate
        self._audit = audit
        self._clock = clock
        self._environment = environment

    def execute(
        self,
        *,
        switch_id: KillSwitchId,
        evidence_account_id: AccountId,
        release_reason: str,
        confirmation_id: DangerousActionConfirmationId,
        correlation_id: CorrelationId | None = None,
    ) -> KillSwitch:
        switch = self._repository.get(switch_id)
        if switch is None:
            raise KillSwitchReleaseDeniedError("KillSwitch was not found.")

        auth_scope = kill_switch_authorization_scope(
            environment=self._environment,
            permission=Permission.RELEASE_KILL_SWITCH,
            switch=switch,
        )
        self._authorize.ensure_allowed(
            permission=Permission.RELEASE_KILL_SWITCH,
            scope=auth_scope,
        )
        principal = self._principal_provider.current_principal()
        scope_reference = f"kill-switch:{switch.id}"
        self._confirmations.consume(
            confirmation_id=confirmation_id,
            actor_id=principal.actor_id,
            action=DangerousAction.RELEASE_KILL_SWITCH,
            scope_reference=scope_reference,
        )

        evidence = self._evidence.get(evidence_account_id)
        if evidence is None:
            raise KillSwitchReleaseDeniedError(
                "KillSwitch release requires current safety evidence."
            )
        decision = self._gate.evaluate(
            action=SafetyAction.RELEASE_KILL_SWITCH,
            evidence=evidence,
            authorization_allowed=True,
            kill_switch_active=False,
        )
        if not decision.allowed:
            raise KillSwitchReleaseDeniedError(
                "Underlying safety state cannot support KillSwitch release."
            )

        released = switch.release(
            actor_id=principal.actor_id,
            reason=release_reason,
            occurred_at=self._clock.now(),
        )
        self._repository.save(released, expected_version=switch.version)
        self._audit.record(
            SafetyAuditEvent(
                event_type="KILL_SWITCH_RELEASED",
                actor_id=principal.actor_id,
                action=SafetyAction.RELEASE_KILL_SWITCH.value,
                scope_reference=scope_reference,
                reason=release_reason,
                occurred_at=self._clock.now(),
                correlation_id=correlation_id,
            )
        )
        return released
