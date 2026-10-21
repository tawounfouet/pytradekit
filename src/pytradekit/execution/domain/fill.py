"""Canonical execution fill fact."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from pytradekit.orders.domain import OrderId
from pytradekit.shared import (
    DomainValidationError,
    Money,
    Price,
    Quantity,
    require_utc_datetime,
)


@dataclass(frozen=True, slots=True)
class FillId:
    """Internal UUID identifier for a fill."""

    value: UUID

    def __post_init__(self) -> None:
        """Validate the identifier representation."""
        if not isinstance(self.value, UUID):
            raise DomainValidationError("FillId value must be a UUID.")

    @classmethod
    def new(cls) -> Self:
        """Create a new fill identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create a fill identifier from a UUID string."""
        if not isinstance(value, str) or not value.strip():
            raise DomainValidationError("FillId string value must be a non-empty string.")
        try:
            return cls(UUID(value.strip()))
        except ValueError as exc:
            raise DomainValidationError("FillId string value must be a valid UUID.") from exc

    def __str__(self) -> str:
        """Return the canonical UUID representation."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Fill:
    """Immutable external execution fact representing an economic fill."""

    id: FillId
    order_id: OrderId
    quantity: Quantity
    price: Price
    occurred_at: datetime
    external_fill_id: str | None = None
    fee: Money | None = None

    def __post_init__(self) -> None:
        """Validate canonical fill invariants."""
        if not isinstance(self.id, FillId):
            raise DomainValidationError("Fill id must be a FillId.")
        if not isinstance(self.order_id, OrderId):
            raise DomainValidationError("Fill order_id must be an OrderId.")
        if not isinstance(self.quantity, Quantity) or self.quantity.value <= 0:
            raise DomainValidationError("Fill quantity must be greater than zero.")
        if not isinstance(self.price, Price):
            raise DomainValidationError("Fill price must be a Price.")
        require_utc_datetime(self.occurred_at, field_name="Fill occurred_at")
        if self.external_fill_id is not None and not self.external_fill_id.strip():
            raise DomainValidationError("Fill external_fill_id must not be empty.")
        if self.fee is not None and not isinstance(self.fee, Money):
            raise DomainValidationError("Fill fee must be Money or None.")

    @property
    def deduplication_key(self) -> str:
        """Return the stable key used to protect against duplicate economic effects."""
        if self.external_fill_id is not None:
            return self.external_fill_id
        return str(self.id)
