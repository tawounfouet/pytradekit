"""Explicit authorization decisions with stable reason semantics."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pytradekit.security.domain.actor_id import ActorId
from pytradekit.security.domain.authorization_scope import AuthorizationScope
from pytradekit.security.domain.permission import Permission
from pytradekit.shared import DomainValidationError, require_utc_datetime


class AuthorizationReason(StrEnum):
    """Stable reason codes for authorization decisions."""

    ALLOWED = "ALLOWED"
    ACTOR_NOT_FOUND = "ACTOR_NOT_FOUND"
    ACTOR_DISABLED = "ACTOR_DISABLED"
    ROLE_MISSING = "ROLE_MISSING"
    PERMISSION_MISSING = "PERMISSION_MISSING"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    ASSIGNMENT_EXPIRED = "ASSIGNMENT_EXPIRED"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Explainable result of one authorization evaluation."""

    allowed: bool
    actor_id: ActorId
    permission: Permission
    scope: AuthorizationScope
    reason_code: AuthorizationReason
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise DomainValidationError("AuthorizationDecision allowed must be a bool.")
        if not isinstance(self.actor_id, ActorId):
            raise DomainValidationError("AuthorizationDecision actor_id is invalid.")
        if not isinstance(self.permission, Permission):
            raise DomainValidationError("AuthorizationDecision permission is invalid.")
        if not isinstance(self.scope, AuthorizationScope):
            raise DomainValidationError("AuthorizationDecision scope is invalid.")
        if not isinstance(self.reason_code, AuthorizationReason):
            raise DomainValidationError("AuthorizationDecision reason_code is invalid.")
        require_utc_datetime(
            self.evaluated_at,
            field_name="AuthorizationDecision evaluated_at",
        )
