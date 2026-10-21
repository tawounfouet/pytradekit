"""Canonical order identifier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class OrderId:
    """Provider-independent UUID identifier for an order."""

    value: UUID

    def __post_init__(self) -> None:
        """Validate the identifier representation."""
        if not isinstance(self.value, UUID):
            raise DomainValidationError("OrderId value must be a UUID.")

    @classmethod
    def new(cls) -> Self:
        """Create a new order identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create an order identifier from a UUID string."""
        if not isinstance(value, str) or not value.strip():
            raise DomainValidationError("OrderId string value must be a non-empty string.")

        try:
            return cls(UUID(value.strip()))
        except ValueError as exc:
            raise DomainValidationError("OrderId string value must be a valid UUID.") from exc

    def __str__(self) -> str:
        """Return the canonical UUID representation."""
        return str(self.value)
