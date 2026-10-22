"""In-memory Security repositories."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime

from pytradekit.security.domain import Actor, ActorId, AuthorizationScope, Role, RoleAssignment, RoleId
from pytradekit.shared import require_utc_datetime


class InMemoryActorRepository:
    def __init__(self) -> None:
        self._actors: dict[ActorId, Actor] = {}

    def save(self, actor: Actor) -> None:
        self._actors[actor.id] = deepcopy(actor)

    def get(self, actor_id: ActorId) -> Actor | None:
        actor = self._actors.get(actor_id)
        return deepcopy(actor) if actor is not None else None


class InMemoryRoleRepository:
    def __init__(self) -> None:
        self._roles: dict[RoleId, Role] = {}

    def save(self, role: Role) -> None:
        self._roles[role.id] = deepcopy(role)

    def get(self, role_id: RoleId) -> Role | None:
        role = self._roles.get(role_id)
        return deepcopy(role) if role is not None else None


class InMemoryRoleAssignmentRepository:
    def __init__(self) -> None:
        self._assignments: list[RoleAssignment] = []

    def add(self, assignment: RoleAssignment) -> None:
        self._assignments.append(deepcopy(assignment))

    def list_for_actor(self, actor_id: ActorId) -> tuple[RoleAssignment, ...]:
        matches = [deepcopy(item) for item in self._assignments if item.actor_id == actor_id]
        matches.sort(key=lambda item: (item.valid_from, str(item.role_id)))
        return tuple(matches)

    def revoke(
        self,
        *,
        actor_id: ActorId,
        role_id: RoleId,
        scope: AuthorizationScope,
        revoked_at: datetime,
    ) -> int:
        timestamp = require_utc_datetime(revoked_at, field_name="RoleAssignment revoked_at")
        count = 0
        updated: list[RoleAssignment] = []
        for assignment in self._assignments:
            if (
                assignment.actor_id == actor_id
                and assignment.role_id == role_id
                and assignment.scope == scope
                and assignment.is_active(timestamp)
            ):
                updated.append(replace(assignment, valid_until=timestamp))
                count += 1
            else:
                updated.append(assignment)
        self._assignments = updated
        return count
