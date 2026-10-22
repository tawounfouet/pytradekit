"""Security actor types."""

from enum import StrEnum


class ActorType(StrEnum):
    """Origin category for an authenticated actor."""

    HUMAN = "HUMAN"
    SERVICE = "SERVICE"
    SYSTEM = "SYSTEM"
