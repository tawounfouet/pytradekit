"""IBKR Contract and ContractDetails mapping into canonical reference models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pytradekit.brokers import ProviderInstrumentIdentity
from pytradekit.reference.domain import (
    AssetClass,
    ContractSpecification,
    Instrument,
    InstrumentMapping,
)
from pytradekit.shared import Currency, InstrumentId

from .discovery import IBKR_PROVIDER_KEY
from .identities import IBKRContractId, IBKRContractIdentity

IBKR_STOCK_SECURITY_TYPE: Final = "STK"
IBKR_TARGET_ROUTING_EXCHANGE: Final = "SMART"
IBKR_TARGET_CURRENCY: Final = "USD"


class IBKRContractMappingError(ValueError):
    """Raised when an IBKR contract cannot be mapped safely."""


class IBKRSecurityType(StrEnum):
    """IBKR security types accepted by the current vertical slice."""

    STOCK = IBKR_STOCK_SECURITY_TYPE


class IBKRPriceIncrementMode(StrEnum):
    """How price increment semantics can be represented canonically."""

    STATIC = "STATIC"
    MARKET_RULE = "MARKET_RULE"
    UNKNOWN = "UNKNOWN"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRContractMappingError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKRContractMappingError(f"{field_name} must be non-empty.")
    return normalized


def _optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name=field_name)


def _positive_decimal(
    value: Decimal | None,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise IBKRContractMappingError(
            f"{field_name} must be a finite positive Decimal or None."
        )
    return value


def _non_negative_decimal(
    value: Decimal | None,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise IBKRContractMappingError(
            f"{field_name} must be a finite non-negative Decimal or None."
        )
    return value


def _normalized_labels(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise IBKRContractMappingError(f"{field_name} must be a tuple.")
    normalized = tuple(_text(value, field_name=field_name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise IBKRContractMappingError(f"{field_name} must not contain duplicates.")
    return normalized


@dataclass(frozen=True, slots=True)
class IBKRContractRecord:
    """SDK-free representation of one qualified IBKR Contract."""

    contract_id: IBKRContractId
    symbol: str
    security_type: IBKRSecurityType
    exchange: str
    primary_exchange: str
    currency: str
    local_symbol: str
    trading_class: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, IBKRContractId):
            raise IBKRContractMappingError(
                "IBKRContractRecord.contract_id must be an IBKRContractId."
            )
        if not isinstance(self.security_type, IBKRSecurityType):
            raise IBKRContractMappingError(
                "IBKRContractRecord.security_type must be an IBKRSecurityType."
            )
        object.__setattr__(
            self,
            "symbol",
            _text(self.symbol, field_name="IBKRContractRecord.symbol"),
        )
        object.__setattr__(
            self,
            "exchange",
            _text(self.exchange, field_name="IBKRContractRecord.exchange").upper(),
        )
        object.__setattr__(
            self,
            "primary_exchange",
            _text(
                self.primary_exchange,
                field_name="IBKRContractRecord.primary_exchange",
            ).upper(),
        )
        object.__setattr__(
            self,
            "currency",
            _text(self.currency, field_name="IBKRContractRecord.currency").upper(),
        )
        object.__setattr__(
            self,
            "local_symbol",
            _text(
                self.local_symbol,
                field_name="IBKRContractRecord.local_symbol",
            ),
        )
        trading_class = _optional_text(
            self.trading_class,
            field_name="IBKRContractRecord.trading_class",
        )
        object.__setattr__(self, "trading_class", trading_class)


@dataclass(frozen=True, slots=True)
class IBKRContractDetailsRecord:
    """SDK-free subset of IBKR ContractDetails required by LOT-05.2."""

    contract: IBKRContractRecord
    min_tick: Decimal | None = None
    min_size: Decimal | None = None
    size_increment: Decimal | None = None
    suggested_size_increment: Decimal | None = None
    valid_exchanges: tuple[str, ...] = ()
    market_rule_ids: tuple[int | None, ...] = ()
    order_types: tuple[str, ...] = ()
    time_zone_id: str | None = None
    stock_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.contract, IBKRContractRecord):
            raise IBKRContractMappingError(
                "IBKRContractDetailsRecord.contract must be an IBKRContractRecord."
            )
        object.__setattr__(
            self,
            "min_tick",
            _positive_decimal(
                self.min_tick,
                field_name="IBKRContractDetailsRecord.min_tick",
            ),
        )
        object.__setattr__(
            self,
            "min_size",
            _non_negative_decimal(
                self.min_size,
                field_name="IBKRContractDetailsRecord.min_size",
            ),
        )
        object.__setattr__(
            self,
            "size_increment",
            _positive_decimal(
                self.size_increment,
                field_name="IBKRContractDetailsRecord.size_increment",
            ),
        )
        object.__setattr__(
            self,
            "suggested_size_increment",
            _positive_decimal(
                self.suggested_size_increment,
                field_name="IBKRContractDetailsRecord.suggested_size_increment",
            ),
        )
        valid_exchanges = _normalized_labels(
            self.valid_exchanges,
            field_name="IBKRContractDetailsRecord.valid_exchanges",
        )
        order_types = _normalized_labels(
            self.order_types,
            field_name="IBKRContractDetailsRecord.order_types",
        )
        object.__setattr__(self, "valid_exchanges", valid_exchanges)
        object.__setattr__(self, "order_types", order_types)

        if not isinstance(self.market_rule_ids, tuple):
            raise IBKRContractMappingError(
                "IBKRContractDetailsRecord.market_rule_ids must be a tuple."
            )
        if any(
            value is not None and (type(value) is not int or value < 0)
            for value in self.market_rule_ids
        ):
            raise IBKRContractMappingError(
                "IBKRContractDetailsRecord.market_rule_ids must contain "
                "non-negative integers or None."
            )
        if (
            self.market_rule_ids
            and valid_exchanges
            and len(self.market_rule_ids) != len(valid_exchanges)
        ):
            raise IBKRContractMappingError(
                "IBKR market_rule_ids and valid_exchanges must preserve positional alignment."
            )

        object.__setattr__(
            self,
            "time_zone_id",
            _optional_text(
                self.time_zone_id,
                field_name="IBKRContractDetailsRecord.time_zone_id",
            ),
        )
        object.__setattr__(
            self,
            "stock_type",
            _optional_text(
                self.stock_type,
                field_name="IBKRContractDetailsRecord.stock_type",
            ),
        )


@dataclass(frozen=True, slots=True)
class IBKRInstrumentMappingResult:
    """Canonical reference mapping plus retained IBKR contract semantics."""

    identity: ProviderInstrumentIdentity
    instrument: Instrument
    mapping: InstrumentMapping
    specification: ContractSpecification
    routing_exchange: str
    primary_exchange: str
    local_symbol: str
    trading_class: str | None
    valid_exchanges: tuple[str, ...]
    market_rule_ids: tuple[int | None, ...]
    price_increment_mode: IBKRPriceIncrementMode
    reported_min_tick: Decimal | None
    suggested_size_increment: Decimal | None
    order_types: tuple[str, ...]
    time_zone_id: str | None
    stock_type: str | None

    def __post_init__(self) -> None:
        if self.instrument.id != self.mapping.instrument_id:
            raise IBKRContractMappingError(
                "IBKR instrument and mapping canonical IDs must match."
            )
        if self.mapping.provider != IBKR_PROVIDER_KEY:
            raise IBKRContractMappingError(
                "IBKR instrument mapping provider must be ibkr."
            )
        if self.identity.external_id != self.mapping.external_id:
            raise IBKRContractMappingError(
                "IBKR provider identity and mapping external IDs must match."
            )
        if self.identity.external_symbol != self.mapping.external_symbol:
            raise IBKRContractMappingError(
                "IBKR provider identity and mapping symbols must match."
            )
        if not isinstance(self.price_increment_mode, IBKRPriceIncrementMode):
            raise IBKRContractMappingError(
                "price_increment_mode must be an IBKRPriceIncrementMode."
            )


def map_ibkr_stock_contract(
    details: IBKRContractDetailsRecord,
    *,
    instrument_id: InstrumentId,
) -> IBKRInstrumentMappingResult:
    """Map a qualified IBKR US stock contract without leaking SDK types."""

    if not isinstance(details, IBKRContractDetailsRecord):
        raise IBKRContractMappingError(
            "details must be an IBKRContractDetailsRecord."
        )
    if not isinstance(instrument_id, InstrumentId):
        raise IBKRContractMappingError("instrument_id must be an InstrumentId.")

    contract = details.contract
    if contract.security_type is not IBKRSecurityType.STOCK:
        raise IBKRContractMappingError(
            "IBKR contract is outside the qualified STK scope."
        )
    if contract.exchange != IBKR_TARGET_ROUTING_EXCHANGE:
        raise IBKRContractMappingError(
            "IBKR LOT-05.2 stock routing exchange must be SMART."
        )
    if contract.currency != IBKR_TARGET_CURRENCY:
        raise IBKRContractMappingError(
            "IBKR LOT-05.2 stock currency must be USD."
        )

    identity = IBKRContractIdentity(
        contract_id=contract.contract_id,
        symbol=contract.symbol,
    ).to_provider_identity()
    currency = Currency(contract.currency)
    instrument = Instrument(
        id=instrument_id,
        symbol=contract.symbol,
        asset_class=AssetClass.EQUITY,
        quote_currency=currency,
    )
    mapping = InstrumentMapping(
        instrument_id=instrument_id,
        provider=IBKR_PROVIDER_KEY,
        external_symbol=identity.external_symbol,
        external_id=identity.external_id,
    )

    price_increment_mode: IBKRPriceIncrementMode
    canonical_tick_size: Decimal | None
    if any(rule_id is not None for rule_id in details.market_rule_ids):
        price_increment_mode = IBKRPriceIncrementMode.MARKET_RULE
        canonical_tick_size = None
    elif details.min_tick is not None:
        price_increment_mode = IBKRPriceIncrementMode.STATIC
        canonical_tick_size = details.min_tick
    else:
        price_increment_mode = IBKRPriceIncrementMode.UNKNOWN
        canonical_tick_size = None

    specification = ContractSpecification(
        tick_size=canonical_tick_size,
        quantity_step=details.size_increment,
        min_quantity=details.min_size,
    )

    return IBKRInstrumentMappingResult(
        identity=identity,
        instrument=instrument,
        mapping=mapping,
        specification=specification,
        routing_exchange=contract.exchange,
        primary_exchange=contract.primary_exchange,
        local_symbol=contract.local_symbol,
        trading_class=contract.trading_class,
        valid_exchanges=details.valid_exchanges,
        market_rule_ids=details.market_rule_ids,
        price_increment_mode=price_increment_mode,
        reported_min_tick=details.min_tick,
        suggested_size_increment=details.suggested_size_increment,
        order_types=details.order_types,
        time_zone_id=details.time_zone_id,
        stock_type=details.stock_type,
    )
