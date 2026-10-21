"""Correlation and causation identifiers."""

from dataclasses import dataclass

from pytradekit.shared.ids import _UUIDIdentifier


@dataclass(frozen=True, slots=True)
class CorrelationId(_UUIDIdentifier):
    """Identifier shared by activities belonging to one logical operation."""


@dataclass(frozen=True, slots=True)
class CausationId(_UUIDIdentifier):
    """Identifier of the action or event that directly caused another event."""
