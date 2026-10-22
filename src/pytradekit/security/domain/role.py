"""Security role definitions."""

from dataclasses import dataclass

from pytradekit.security.domain.permission_set import PermissionSet
from pytradekit.security.domain.role_id import RoleId
from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class Role:
    """Named permission bundle without implicit safety privileges."""

    id: RoleId
    name: str
    permissions: PermissionSet

    def __post_init__(self) -> None:
        if not isinstance(self.id, RoleId):
            raise DomainValidationError("Role id must be a RoleId.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainValidationError("Role name must be a non-empty string.")
        if not isinstance(self.permissions, PermissionSet):
            raise DomainValidationError("Role permissions must be a PermissionSet.")
        object.__setattr__(self, "name", self.name.strip())
