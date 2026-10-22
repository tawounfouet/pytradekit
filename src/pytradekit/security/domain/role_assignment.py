"""Time-bound scoped role assignment."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.security.domain.actor_id import ActorId
from pytradekit.security.domain.authorization_scope import AuthorizationScope
from pytradekit.security.domain.role_id import RoleId
from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    """Assign a role inside an explicit scope and validity window."""

    actor_id: ActorId
    role_id: RoleId
    scope: AuthorizationScope
    valid_from: datetime
    assigned_by: ActorId
    created_at: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, ActorId):
            raise DomainValidationError("RoleAssignment actor_id is invalid.")
        if not isinstance(self.role_id, RoleId):
            raise DomainValidationError("RoleAssignment role_id is invalid.")
        if not isinstance(self.scope, AuthorizationScope):
            raise DomainValidationError("RoleAssignment scope is invalid.")
        if not isinstance(self.assigned_by, ActorId):
            raise DomainValidationError("RoleAssignment assigned_by is invalid.")
        require_utc_datetime(self.valid_from, field_name="RoleAssignment valid_from")
        require_utc_datetime(self.created_at, field_name="RoleAssignment created_at")
        if self.valid_until is not None:
            require_utc_datetime(self.valid_until, field_name="RoleAssignment valid_until")
            if self.valid_until <= self.valid_from:
                raise DomainValidationError("valid_until must be after valid_from.")

    def is_active(self, at: datetime) -> bool:
        now = require_utc_datetime(at, field_name="RoleAssignment evaluation time")
        return now >= self.valid_from and (
            self.valid_until is None or now < self.valid_until
        )
