"""Dangerous action confirmation use cases."""

from datetime import timedelta

from pytradekit.runtime.ports import ClockPort
from pytradekit.safety.domain import (
    DangerousAction,
    DangerousActionConfirmation,
    DangerousActionConfirmationId,
    SafetyAuditEvent,
)
from pytradekit.safety.domain.errors import DangerousActionConfirmationError
from pytradekit.safety.ports import (
    DangerousActionConfirmationRepository,
    SafetyAuditSink,
)
from pytradekit.security.domain import ActorId
from pytradekit.security.ports import PrincipalProvider
from pytradekit.shared import CorrelationId


class ConfirmDangerousAction:
    """Create short-lived confirmation evidence without granting authorization."""

    def __init__(
        self,
        *,
        principal_provider: PrincipalProvider,
        repository: DangerousActionConfirmationRepository,
        audit: SafetyAuditSink,
        clock: ClockPort,
        process_nonce: str,
    ) -> None:
        self._principal_provider = principal_provider
        self._repository = repository
        self._audit = audit
        self._clock = clock
        self._process_nonce = process_nonce

    def execute(
        self,
        *,
        action: DangerousAction,
        scope_reference: str,
        challenge_reference: str,
        ttl: timedelta = timedelta(minutes=5),
        correlation_id: CorrelationId | None = None,
    ) -> DangerousActionConfirmation:
        if ttl <= timedelta(0) or ttl > timedelta(minutes=15):
            raise ValueError("Dangerous confirmation TTL must be within 15 minutes.")
        principal = self._principal_provider.current_principal()
        now = self._clock.now()
        confirmation = DangerousActionConfirmation(
            id=DangerousActionConfirmationId.new(),
            actor_id=principal.actor_id,
            action=action,
            scope_reference=scope_reference,
            challenge_reference=challenge_reference,
            confirmed_at=now,
            expires_at=now + ttl,
            process_nonce=self._process_nonce,
        )
        self._repository.save(confirmation)
        self._audit.record(
            SafetyAuditEvent(
                event_type="DANGEROUS_ACTION_CONFIRMED",
                actor_id=principal.actor_id,
                action=action.value,
                scope_reference=scope_reference,
                reason="Explicit confirmation recorded.",
                occurred_at=now,
                correlation_id=correlation_id,
            )
        )
        return confirmation


class ValidateDangerousActionConfirmation:
    """Validate and consume confirmation evidence exactly once."""

    def __init__(
        self,
        *,
        repository: DangerousActionConfirmationRepository,
        clock: ClockPort,
        process_nonce: str,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._process_nonce = process_nonce

    def consume(
        self,
        *,
        confirmation_id: DangerousActionConfirmationId,
        actor_id: ActorId,
        action: DangerousAction,
        scope_reference: str,
    ) -> DangerousActionConfirmation:
        confirmation = self._repository.get(confirmation_id)
        now = self._clock.now()
        if confirmation is None or not confirmation.is_valid(
            actor_id=actor_id,
            action=action,
            scope_reference=scope_reference,
            at=now,
            process_nonce=self._process_nonce,
        ):
            raise DangerousActionConfirmationError(
                "Dangerous action confirmation is invalid or expired."
            )
        consumed = confirmation.consume(occurred_at=now)
        self._repository.save(consumed)
        return consumed
