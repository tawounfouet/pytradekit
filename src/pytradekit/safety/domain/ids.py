"""Typed safety governance identifiers."""

from dataclasses import dataclass

from pytradekit.shared.ids import _UUIDIdentifier


@dataclass(frozen=True, slots=True)
class KillSwitchId(_UUIDIdentifier):
    """Identifier for one kill-switch lifecycle."""


@dataclass(frozen=True, slots=True)
class RiskOverrideId(_UUIDIdentifier):
    """Identifier for one risk-override request."""


@dataclass(frozen=True, slots=True)
class DangerousActionConfirmationId(_UUIDIdentifier):
    """Identifier for one dangerous-action confirmation."""
