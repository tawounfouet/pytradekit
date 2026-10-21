"""Canonical portfolio account identifier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from pytradekit.shared import DomainValidationError


@dataclass(frozen=True, slots=True)
class AccountId:
    """Internal provider-independent UUID identifier for an account."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise DomainValidationError("AccountId value must be a UUID.")

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> Self:
        if not isinstance(value, str) or not value.strip():
            raise DomainValidationError("AccountId string value must be a non-empty string.")
        try:
            return cls(UUID(value.strip()))
        except ValueError as exc:
            raise DomainValidationError("AccountId string value must be a valid UUID.") from exc

    def __str__(self) -> str:
        return str(self.value)
