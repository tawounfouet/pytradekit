"""Security actor aggregate."""

from dataclasses import dataclass

from pytradekit.security.domain.actor_id import ActorId
from pytradekit.security.domain.actor_type import ActorType
from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class Actor:
    """Canonical actor independent from authentication provider details."""

    id: ActorId
    type: ActorType
    display_name: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, ActorId):
            raise DomainValidationError("Actor id must be an ActorId.")
        if not isinstance(self.type, ActorType):
            raise DomainValidationError("Actor type must be an ActorType.")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise DomainValidationError("Actor display_name must be a non-empty string.")
        if type(self.enabled) is not bool:
            raise DomainValidationError("Actor enabled must be a bool.")
        object.__setattr__(self, "display_name", self.display_name.strip())
