"""Canonical snapshots used by reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import Currency, DomainValidationError, InstrumentId, require_utc_datetime

from .enums import ExternalActivityOrigin, SnapshotCompleteness


def _optional_identity(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} must not be empty.")
    return normalized


def _finite(value: Decimal, *, field_name: str, non_negative: bool = False) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise DomainValidationError(f"{field_name} must be a finite Decimal.")
    if non_negative and value < 0:
        raise DomainValidationError(f"{field_name} must be non-negative.")
    return value


@dataclass(frozen=True, slots=True)
class SnapshotWatermark:
    """Evidence describing the cut at which a snapshot is meaningful."""

    captured_at: datetime
    internal_version: int | None = None
    max_event_sequence: int | None = None
    provider_as_of: datetime | None = None
    provider_cursor: str | None = None

    def __post_init__(self) -> None:
        require_utc_datetime(self.captured_at, field_name="SnapshotWatermark captured_at")
        for field_name, value in (
            ("internal_version", self.internal_version),
            ("max_event_sequence", self.max_event_sequence),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise DomainValidationError(f"{field_name} must be a non-negative integer.")
        if self.provider_as_of is not None:
            require_utc_datetime(
                self.provider_as_of,
                field_name="SnapshotWatermark provider_as_of",
            )
        if self.provider_cursor is not None and not self.provider_cursor.strip():
            raise DomainValidationError("provider_cursor must not be empty.")


@dataclass(frozen=True, slots=True)
class CanonicalOrder:
    """Provider-neutral order observation used only for comparison."""

    order_id: OrderId | None
    client_order_id: str | None
    external_order_id: str | None
    status: str
    filled_quantity: Decimal
    cancel_requested: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "client_order_id",
            _optional_identity(self.client_order_id, field_name="client_order_id"),
        )
        object.__setattr__(
            self,
            "external_order_id",
            _optional_identity(self.external_order_id, field_name="external_order_id"),
        )
        if self.order_id is None and self.client_order_id is None and self.external_order_id is None:
            raise DomainValidationError("CanonicalOrder requires at least one stable identity.")
        if not isinstance(self.status, str) or not self.status.strip():
            raise DomainValidationError("CanonicalOrder status must be a non-empty string.")
        _finite(self.filled_quantity, field_name="filled_quantity", non_negative=True)


@dataclass(frozen=True, slots=True)
class CanonicalFill:
    """Canonical execution fact observed internally or externally."""

    external_fill_id: str
    order_id: OrderId | None
    external_order_id: str | None
    quantity: Decimal
    price: Decimal
    currency: Currency
    occurred_at: datetime
    origin: ExternalActivityOrigin = ExternalActivityOrigin.INTERNAL

    def __post_init__(self) -> None:
        external_fill_id = self.external_fill_id.strip()
        if not external_fill_id:
            raise DomainValidationError("CanonicalFill external_fill_id must not be empty.")
        object.__setattr__(self, "external_fill_id", external_fill_id)
        object.__setattr__(
            self,
            "external_order_id",
            _optional_identity(self.external_order_id, field_name="external_order_id"),
        )
        if self.order_id is None and self.external_order_id is None:
            raise DomainValidationError("CanonicalFill requires an order identity.")
        quantity = _finite(self.quantity, field_name="quantity")
        if quantity <= 0:
            raise DomainValidationError("CanonicalFill quantity must be greater than zero.")
        price = _finite(self.price, field_name="price")
        if price <= 0:
            raise DomainValidationError("CanonicalFill price must be greater than zero.")
        if not isinstance(self.currency, Currency):
            raise DomainValidationError("CanonicalFill currency must be a Currency.")
        require_utc_datetime(self.occurred_at, field_name="CanonicalFill occurred_at")


@dataclass(frozen=True, slots=True)
class CanonicalPosition:
    """Canonical position observation."""

    instrument_id: InstrumentId
    quantity: Decimal
    average_price: Decimal | None
    currency: Currency | None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("CanonicalPosition instrument_id must be an InstrumentId.")
        _finite(self.quantity, field_name="position quantity")
        if self.average_price is not None:
            average = _finite(self.average_price, field_name="average_price")
            if average <= 0:
                raise DomainValidationError("average_price must be greater than zero.")
        if self.currency is not None and not isinstance(self.currency, Currency):
            raise DomainValidationError("CanonicalPosition currency must be Currency or None.")


@dataclass(frozen=True, slots=True)
class CanonicalBalance:
    """Canonical cash observation."""

    currency: Currency
    cash: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.currency, Currency):
            raise DomainValidationError("CanonicalBalance currency must be a Currency.")
        _finite(self.cash, field_name="cash")


@dataclass(frozen=True, slots=True)
class InternalSnapshot:
    """Durable PyTradeKit economic state at a known cut."""

    account_id: AccountId
    orders: tuple[CanonicalOrder, ...]
    fills: tuple[CanonicalFill, ...]
    positions: tuple[CanonicalPosition, ...]
    balances: tuple[CanonicalBalance, ...]
    captured_at: datetime
    watermark: SnapshotWatermark
    completeness: SnapshotCompleteness

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, AccountId):
            raise DomainValidationError("InternalSnapshot account_id must be an AccountId.")
        require_utc_datetime(self.captured_at, field_name="InternalSnapshot captured_at")


@dataclass(frozen=True, slots=True)
class BrokerSnapshot:
    """Normalized broker truth at a known cut."""

    account_id: AccountId
    provider: str
    orders: tuple[CanonicalOrder, ...]
    fills: tuple[CanonicalFill, ...]
    positions: tuple[CanonicalPosition, ...]
    balances: tuple[CanonicalBalance, ...]
    captured_at: datetime
    watermark: SnapshotWatermark
    completeness: SnapshotCompleteness

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, AccountId):
            raise DomainValidationError("BrokerSnapshot account_id must be an AccountId.")
        provider = self.provider.strip() if isinstance(self.provider, str) else ""
        if not provider:
            raise DomainValidationError("BrokerSnapshot provider must be a non-empty string.")
        object.__setattr__(self, "provider", provider)
        require_utc_datetime(self.captured_at, field_name="BrokerSnapshot captured_at")
