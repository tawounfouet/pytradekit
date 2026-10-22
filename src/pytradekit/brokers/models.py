"""Provider-neutral broker integration models used by anti-corruption layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.reference.domain import ContractSpecification, Instrument, InstrumentMapping
from pytradekit.shared import (
    CorrelationId,
    Currency,
    DomainValidationError,
    InstrumentId,
    Money,
    Price,
    require_utc_datetime,
)


def _non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise DomainValidationError(f"{field_name} must be a non-empty string.")
    return normalized


@dataclass(frozen=True, slots=True)
class ProviderOrderIdentity:
    """Provider-side order identities kept separate from canonical OrderId."""

    provider: str
    client_reference: str
    external_order_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _non_empty(self.provider, field_name="provider"))
        object.__setattr__(
            self,
            "client_reference",
            _non_empty(self.client_reference, field_name="client_reference"),
        )
        object.__setattr__(
            self,
            "external_order_id",
            _non_empty(self.external_order_id, field_name="external_order_id"),
        )


@dataclass(frozen=True, slots=True)
class ProviderFillIdentity:
    """Provider-side execution identity used for economic deduplication."""

    provider: str
    external_fill_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _non_empty(self.provider, field_name="provider"))
        object.__setattr__(
            self,
            "external_fill_id",
            _non_empty(self.external_fill_id, field_name="external_fill_id"),
        )


@dataclass(frozen=True, slots=True)
class ProviderAccountIdentity:
    """Provider-side account identity mapped to a canonical AccountId elsewhere."""

    provider: str
    external_account_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _non_empty(self.provider, field_name="provider"))
        object.__setattr__(
            self,
            "external_account_id",
            _non_empty(self.external_account_id, field_name="external_account_id"),
        )


@dataclass(frozen=True, slots=True)
class ProviderInstrumentIdentity:
    """Provider-side instrument identity mapped to canonical InstrumentId."""

    provider: str
    external_id: str
    external_symbol: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _non_empty(self.provider, field_name="provider"))
        object.__setattr__(
            self,
            "external_id",
            _non_empty(self.external_id, field_name="external_id"),
        )
        object.__setattr__(
            self,
            "external_symbol",
            _non_empty(self.external_symbol, field_name="external_symbol"),
        )


@dataclass(frozen=True, slots=True)
class ProviderExecutionContext:
    """Canonical context required to translate provider order facts safely."""

    order_id: OrderId
    correlation_id: CorrelationId
    client_order_reference: str
    quote_currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, OrderId):
            raise DomainValidationError("ProviderExecutionContext order_id must be an OrderId.")
        if not isinstance(self.correlation_id, CorrelationId):
            raise DomainValidationError(
                "ProviderExecutionContext correlation_id must be a CorrelationId."
            )
        object.__setattr__(
            self,
            "client_order_reference",
            _non_empty(
                self.client_order_reference,
                field_name="client_order_reference",
            ),
        )
        if not isinstance(self.quote_currency, Currency):
            raise DomainValidationError(
                "ProviderExecutionContext quote_currency must be a Currency."
            )


@dataclass(frozen=True, slots=True)
class ProviderAccountSnapshot:
    """Canonical account observations translated from one provider snapshot."""

    identity: ProviderAccountIdentity
    account: Account
    cash_balance: Balance | None
    equity: Money | None
    buying_power: Money | None
    portfolio_value: Money | None
    trading_blocked: bool
    account_blocked: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProviderAccountIdentity):
            raise DomainValidationError("ProviderAccountSnapshot identity is invalid.")
        if not isinstance(self.account, Account):
            raise DomainValidationError("ProviderAccountSnapshot account is invalid.")
        if self.cash_balance is not None and self.cash_balance.account_id != self.account.id:
            raise DomainValidationError("ProviderAccountSnapshot balance account mismatch.")
        for field_name, value in (
            ("equity", self.equity),
            ("buying_power", self.buying_power),
            ("portfolio_value", self.portfolio_value),
        ):
            if value is not None and value.currency != self.account.base_currency:
                raise DomainValidationError(
                    f"ProviderAccountSnapshot {field_name} currency mismatch."
                )
        require_utc_datetime(self.observed_at, field_name="ProviderAccountSnapshot observed_at")


@dataclass(frozen=True, slots=True)
class ProviderPositionSnapshot:
    """Provider position observation using canonical identifiers and Decimal values."""

    account_id: AccountId
    instrument_id: InstrumentId
    provider_instrument: ProviderInstrumentIdentity
    signed_quantity: Decimal
    average_price: Price
    market_value: Money | None
    cost_basis: Money
    unrealized_pnl: Money | None
    current_price: Price | None
    available_quantity: Decimal | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, AccountId):
            raise DomainValidationError("ProviderPositionSnapshot account_id is invalid.")
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("ProviderPositionSnapshot instrument_id is invalid.")
        if not isinstance(self.signed_quantity, Decimal) or not self.signed_quantity.is_finite():
            raise DomainValidationError(
                "ProviderPositionSnapshot signed_quantity must be a finite Decimal."
            )
        if self.average_price.currency != self.cost_basis.currency:
            raise DomainValidationError("ProviderPositionSnapshot currency mismatch.")
        if (
            self.market_value is not None
            and self.market_value.currency != self.cost_basis.currency
        ):
            raise DomainValidationError(
                "ProviderPositionSnapshot market_value currency mismatch."
            )
        if (
            self.unrealized_pnl is not None
            and self.unrealized_pnl.currency != self.cost_basis.currency
        ):
            raise DomainValidationError(
                "ProviderPositionSnapshot unrealized_pnl currency mismatch."
            )
        if (
            self.current_price is not None
            and self.current_price.currency != self.cost_basis.currency
        ):
            raise DomainValidationError(
                "ProviderPositionSnapshot current_price currency mismatch."
            )
        if self.available_quantity is not None and (
            not self.available_quantity.is_finite() or self.available_quantity < 0
        ):
            raise DomainValidationError(
                "ProviderPositionSnapshot available_quantity must be non-negative."
            )
        require_utc_datetime(self.observed_at, field_name="ProviderPositionSnapshot observed_at")


@dataclass(frozen=True, slots=True)
class ProviderInstrumentSnapshot:
    """Canonical instrument, mapping, constraints, and provider capability observations."""

    identity: ProviderInstrumentIdentity
    instrument: Instrument
    mapping: InstrumentMapping
    specification: ContractSpecification
    provider_exchange: str
    provider_status: str
    tradable: bool
    marginable: bool
    shortable: bool
    easy_to_borrow: bool
    fractionable: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.instrument.id != self.mapping.instrument_id:
            raise DomainValidationError("ProviderInstrumentSnapshot instrument mapping mismatch.")
        if self.mapping.external_id != self.identity.external_id:
            raise DomainValidationError("ProviderInstrumentSnapshot external ID mismatch.")
        if self.mapping.external_symbol != self.identity.external_symbol:
            raise DomainValidationError("ProviderInstrumentSnapshot external symbol mismatch.")
        _non_empty(self.provider_exchange, field_name="provider_exchange")
        _non_empty(self.provider_status, field_name="provider_status")
        require_utc_datetime(
            self.observed_at,
            field_name="ProviderInstrumentSnapshot observed_at",
        )


@dataclass(frozen=True, slots=True)
class ProviderOrderStateSnapshot:
    """Provider order observation that may not yet be safe to turn into an execution fact."""

    order_id: OrderId
    identity: ProviderOrderIdentity
    provider_status: str
    canonical_status: ExecutionStatus | None
    filled_quantity: Decimal
    filled_average_price: Decimal | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, OrderId):
            raise DomainValidationError("ProviderOrderStateSnapshot order_id is invalid.")
        _non_empty(self.provider_status, field_name="provider_status")
        if not self.filled_quantity.is_finite() or self.filled_quantity < 0:
            raise DomainValidationError(
                "ProviderOrderStateSnapshot filled_quantity must be non-negative."
            )
        if self.filled_average_price is not None and (
            not self.filled_average_price.is_finite() or self.filled_average_price <= 0
        ):
            raise DomainValidationError(
                "ProviderOrderStateSnapshot filled_average_price must be positive."
            )
        require_utc_datetime(
            self.observed_at,
            field_name="ProviderOrderStateSnapshot observed_at",
        )
