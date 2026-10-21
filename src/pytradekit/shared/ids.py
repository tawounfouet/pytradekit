"""Typed UUID identifiers used by the PyTradeKit domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from pytradekit.shared.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class _UUIDIdentifier:
    """Internal immutable base for strongly typed UUID identifiers."""

    value: UUID

    def __post_init__(self) -> None:
        """Validate the canonical UUID representation."""
        raw_value: object = self.value

        if not isinstance(raw_value, UUID):
            raise DomainValidationError(
                f"{type(self).__name__} value must be a UUID."
            )

    @classmethod
    def new(cls) -> Self:
        """Create a new identifier backed by a random UUID."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create an identifier from a UUID string."""
        raw_value: object = value

        if not isinstance(raw_value, str):
            raise DomainValidationError(
                f"{cls.__name__} string value must be a string."
            )

        normalized = raw_value.strip()

        if not normalized:
            raise DomainValidationError(
                f"{cls.__name__} string value must not be empty."
            )

        try:
            parsed = UUID(normalized)
        except ValueError as exc:
            raise DomainValidationError(
                f"{cls.__name__} string value must be a valid UUID."
            ) from exc

        return cls(parsed)

    def __str__(self) -> str:
        """Return the canonical UUID string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class InstrumentId(_UUIDIdentifier):
    """Canonical provider-independent identifier for an instrument."""


@dataclass(frozen=True, slots=True)
class EventId(_UUIDIdentifier):
    """Canonical identifier for a domain event."""
