"""Security repository ports."""

from datetime import datetime
from typing import Protocol

from pytradekit.security.domain import Actor, ActorId, AuthorizationScope, Role, RoleAssignment, RoleId


class ActorRepository(Protocol):
    def save(self, actor: Actor) -> None: ...
    def get(self, actor_id: ActorId) -> Actor | None: ...


class RoleRepository(Protocol):
    def save(self, role: Role) -> None: ...
    def get(self, role_id: RoleId) -> Role | None: ...


class RoleAssignmentRepository(Protocol):
    def add(self, assignment: RoleAssignment) -> None: ...
    def list_for_actor(self, actor_id: ActorId) -> tuple[RoleAssignment, ...]: ...
    def revoke(
        self,
        *,
        actor_id: ActorId,
        role_id: RoleId,
        scope: AuthorizationScope,
        revoked_at: datetime,
    ) -> int: ...
