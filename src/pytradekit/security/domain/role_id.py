"""Canonical security role identifier."""

from dataclasses import dataclass

from pytradekit.shared.ids import _UUIDIdentifier


@dataclass(frozen=True, slots=True)
class RoleId(_UUIDIdentifier):
    """UUID identifier for a role definition."""
