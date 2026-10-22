"""Authenticated principal evidence and context."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.security.domain.actor_id import ActorId
from pytradekit.security.domain.authorization_scope import AuthorizationEnvironment
from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Identity evidence supplied by an authentication boundary."""

    actor_id: ActorId
    authentication_method: str
    authenticated_at: datetime
    session_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, ActorId):
            raise DomainValidationError("AuthenticatedPrincipal actor_id is invalid.")
        if not isinstance(self.authentication_method, str) or not self.authentication_method.strip():
            raise DomainValidationError("authentication_method must be non-empty.")
        require_utc_datetime(self.authenticated_at, field_name="authenticated_at")
        object.__setattr__(self, "authentication_method", self.authentication_method.strip())
        if self.session_reference is not None:
            if not isinstance(self.session_reference, str) or not self.session_reference.strip():
                raise DomainValidationError("session_reference must be non-empty.")
            object.__setattr__(self, "session_reference", self.session_reference.strip())


@dataclass(frozen=True, slots=True)
class PrincipalContext:
    """Current principal plus environment and optional account context."""

    principal: AuthenticatedPrincipal
    environment: AuthorizationEnvironment
    account_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.principal, AuthenticatedPrincipal):
            raise DomainValidationError("PrincipalContext principal is invalid.")
        if not isinstance(self.environment, AuthorizationEnvironment):
            raise DomainValidationError("PrincipalContext environment is invalid.")
        if self.account_id is not None:
            if not isinstance(self.account_id, str) or not self.account_id.strip():
                raise DomainValidationError("PrincipalContext account_id must be non-empty.")
            object.__setattr__(self, "account_id", self.account_id.strip())
