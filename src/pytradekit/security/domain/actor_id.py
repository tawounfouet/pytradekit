"""Canonical security actor identifier."""

from dataclasses import dataclass

from pytradekit.shared.ids import _UUIDIdentifier


@dataclass(frozen=True, slots=True)
class ActorId(_UUIDIdentifier):
    """Provider-independent UUID identifier for an actor."""
