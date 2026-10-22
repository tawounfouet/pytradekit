"""Typed identifiers for reconciliation evidence."""

from dataclasses import dataclass

from pytradekit.shared.ids import _UUIDIdentifier


@dataclass(frozen=True, slots=True)
class ReconciliationRunId(_UUIDIdentifier):
    """Identifier for one reconciliation run."""


@dataclass(frozen=True, slots=True)
class MismatchId(_UUIDIdentifier):
    """Identifier for one detected mismatch."""


@dataclass(frozen=True, slots=True)
class ResolutionId(_UUIDIdentifier):
    """Identifier for one mismatch resolution."""
