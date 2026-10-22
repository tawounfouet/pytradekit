"""Time-bound confirmation evidence for dangerous actions."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from pytradekit.safety.domain.ids import DangerousActionConfirmationId
from pytradekit.security.domain import ActorId
from pytradekit.shared import DomainValidationError, require_utc_datetime


class DangerousAction(StrEnum):
    """Actions requiring extra human or operator confirmation."""

    RELEASE_KILL_SWITCH = "RELEASE_KILL_SWITCH"
    CREATE_RISK_OVERRIDE = "CREATE_RISK_OVERRIDE"
    REVOKE_RISK_OVERRIDE = "REVOKE_RISK_OVERRIDE"
    MANAGE_ROLE_ASSIGNMENT = "MANAGE_ROLE_ASSIGNMENT"


@dataclass(frozen=True, slots=True)
class DangerousActionConfirmation:
    """Short-lived confirmation evidence distinct from authorization."""

    id: DangerousActionConfirmationId
    actor_id: ActorId
    action: DangerousAction
    scope_reference: str
    challenge_reference: str
    confirmed_at: datetime
    expires_at: datetime
    process_nonce: str
    consumed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, DangerousActionConfirmationId):
            raise DomainValidationError("Confirmation id is invalid.")
        if not isinstance(self.actor_id, ActorId):
            raise DomainValidationError("Confirmation actor_id is invalid.")
        for field_name in (
            "scope_reference",
            "challenge_reference",
            "process_nonce",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise DomainValidationError(
                    f"Confirmation {field_name} must be non-empty."
                )
        require_utc_datetime(
            self.confirmed_at,
            field_name="Confirmation confirmed_at",
        )
        require_utc_datetime(self.expires_at, field_name="Confirmation expires_at")
        if self.expires_at <= self.confirmed_at:
            raise DomainValidationError(
                "Confirmation expires_at must be after confirmed_at."
            )
        if self.consumed_at is not None:
            require_utc_datetime(
                self.consumed_at,
                field_name="Confirmation consumed_at",
            )

    def is_valid(
        self,
        *,
        actor_id: ActorId,
        action: DangerousAction,
        scope_reference: str,
        at: datetime,
        process_nonce: str,
    ) -> bool:
        now = require_utc_datetime(at, field_name="Confirmation evaluation time")
        return (
            self.consumed_at is None
            and self.actor_id == actor_id
            and self.action is action
            and self.scope_reference == scope_reference
            and self.process_nonce == process_nonce
            and self.confirmed_at <= now < self.expires_at
        )

    def consume(self, *, occurred_at: datetime) -> "DangerousActionConfirmation":
        if self.consumed_at is not None:
            raise DomainValidationError("Confirmation has already been consumed.")
        now = require_utc_datetime(
            occurred_at,
            field_name="Confirmation consumption time",
        )
        return replace(self, consumed_at=now)
