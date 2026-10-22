"""Immutable permission bundles."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Self

from pytradekit.security.domain.permission import Permission
from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class PermissionSet:
    """Immutable role permission set."""

    permissions: frozenset[Permission]

    def __post_init__(self) -> None:
        if not isinstance(self.permissions, frozenset):
            raise DomainValidationError("PermissionSet permissions must be a frozenset.")
        if any(not isinstance(permission, Permission) for permission in self.permissions):
            raise DomainValidationError("PermissionSet contains an invalid permission.")

    @classmethod
    def of(cls, *permissions: Permission) -> Self:
        """Build a permission set from explicit permissions."""
        return cls(frozenset(permissions))

    def __contains__(self, permission: Permission) -> bool:
        return permission in self.permissions

    def __iter__(self) -> Iterator[Permission]:
        return iter(self.permissions)

    def __len__(self) -> int:
        return len(self.permissions)
