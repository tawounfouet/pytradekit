"""IBKR dynamic market-rule resolution and LIMIT price validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Protocol, cast

from pytradekit.brokers import (
    ProviderProtocolError,
    ProviderUnavailableError,
)

from .contract_mapping import IBKRInstrumentMappingResult
from .discovery import IBKR_PROVIDER_KEY
from .runtime import IBKRPaperConnectionRuntime

IBKR_MARKET_RULE_VERSION = "0.8.0b7-lot06.6"


class IBKRMarketRuleError(ValueError):
    """Raised when market-rule data cannot validate a price safely."""


class IBKRMarketRuleClient(Protocol):
    """Provider-local request surface required for dynamic price increments."""

    def reqMarketRule(self, marketRuleId: int) -> object:
        """Return provider price increments for one market rule."""

        ...


@dataclass(frozen=True, slots=True)
class IBKRPriceIncrement:
    """SDK-free price increment active from one inclusive low edge."""

    low_edge: Decimal
    increment: Decimal

    def __post_init__(self) -> None:
        if (
            not isinstance(self.low_edge, Decimal)
            or not self.low_edge.is_finite()
            or self.low_edge < 0
        ):
            raise IBKRMarketRuleError(
                "IBKR market-rule low_edge must be a finite non-negative Decimal."
            )
        if (
            not isinstance(self.increment, Decimal)
            or not self.increment.is_finite()
            or self.increment <= 0
        ):
            raise IBKRMarketRuleError(
                "IBKR market-rule increment must be a finite positive Decimal."
            )


@dataclass(frozen=True, slots=True)
class IBKRMarketRule:
    """Qualified SDK-free market rule returned by IBKR."""

    market_rule_id: int
    increments: tuple[IBKRPriceIncrement, ...]

    def __post_init__(self) -> None:
        if type(self.market_rule_id) is not int or self.market_rule_id <= 0:
            raise IBKRMarketRuleError(
                "market_rule_id must be a positive int."
            )
        if not isinstance(self.increments, tuple) or not self.increments:
            raise IBKRMarketRuleError(
                "IBKR market rule must contain at least one price increment."
            )
        if any(
            not isinstance(item, IBKRPriceIncrement)
            for item in self.increments
        ):
            raise IBKRMarketRuleError(
                "increments must contain IBKRPriceIncrement values."
            )

        previous: Decimal | None = None
        for item in self.increments:
            if previous is not None and item.low_edge <= previous:
                raise IBKRMarketRuleError(
                    "IBKR market-rule low edges must be strictly increasing."
                )
            previous = item.low_edge

    def active_increment(self, price: Decimal) -> IBKRPriceIncrement:
        """Return the increment active at the supplied positive price."""

        normalized = _positive_decimal(price, field_name="price")
        active: IBKRPriceIncrement | None = None
        for item in self.increments:
            if item.low_edge > normalized:
                break
            active = item
        if active is None:
            raise IBKRMarketRuleError(
                "IBKR market rule has no increment covering the supplied price."
            )
        return active

    def validates(self, price: Decimal) -> bool:
        """Return whether price conforms to the active market-rule grid."""

        normalized = _positive_decimal(price, field_name="price")
        active = self.active_increment(normalized)
        try:
            remainder = (normalized - active.low_edge) % active.increment
        except InvalidOperation as exc:
            raise IBKRMarketRuleError(
                "IBKR market-rule price arithmetic failed."
            ) from exc
        return remainder == 0


@dataclass(frozen=True, slots=True)
class IBKRMarketRuleResolution:
    """One resolved market rule plus cache evidence."""

    rule: IBKRMarketRule
    cache_hit: bool
    provider_increment_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.rule, IBKRMarketRule):
            raise IBKRMarketRuleError("rule must be an IBKRMarketRule.")
        if type(self.cache_hit) is not bool:
            raise IBKRMarketRuleError("cache_hit must be a bool.")
        if (
            type(self.provider_increment_count) is not int
            or self.provider_increment_count < 0
        ):
            raise IBKRMarketRuleError(
                "provider_increment_count must be a non-negative int."
            )
        if self.cache_hit and self.provider_increment_count != 0:
            raise IBKRMarketRuleError(
                "cache hits must not claim a provider response count."
            )


@dataclass(frozen=True, slots=True)
class IBKRMarketRuleValidationEvidence:
    """Sanitized evidence for one dynamic LIMIT price decision."""

    routing_exchange: str
    market_rule_id: int
    price: Decimal
    low_edge: Decimal
    increment: Decimal
    valid: bool
    cache_hit: bool

    def __post_init__(self) -> None:
        if not isinstance(self.routing_exchange, str) or not self.routing_exchange:
            raise IBKRMarketRuleError(
                "routing_exchange must be non-empty."
            )
        if type(self.market_rule_id) is not int or self.market_rule_id <= 0:
            raise IBKRMarketRuleError(
                "market_rule_id must be a positive int."
            )
        _positive_decimal(self.price, field_name="price")
        if (
            not isinstance(self.low_edge, Decimal)
            or not self.low_edge.is_finite()
            or self.low_edge < 0
        ):
            raise IBKRMarketRuleError(
                "low_edge must be a finite non-negative Decimal."
            )
        _positive_decimal(self.increment, field_name="increment")
        if type(self.valid) is not bool or type(self.cache_hit) is not bool:
            raise IBKRMarketRuleError(
                "valid and cache_hit must be bool values."
            )


class IBKRRuntimeMarketRuleClient:
    """Proxy reqMarketRule through a started PAPER connection runtime."""

    def __init__(self, connection: IBKRPaperConnectionRuntime) -> None:
        if not isinstance(connection, IBKRPaperConnectionRuntime):
            raise IBKRMarketRuleError(
                "connection must be an IBKRPaperConnectionRuntime."
            )
        self._connection = connection

    def reqMarketRule(self, marketRuleId: int) -> object:
        provider = self._connection.read_client()
        if not hasattr(provider, "reqMarketRule"):
            raise ProviderProtocolError(
                "IBKR PAPER client lacks reqMarketRule.",
                provider=IBKR_PROVIDER_KEY,
                operation="reqMarketRule",
            )
        request = cast(IBKRMarketRuleClient, provider)
        try:
            return request.reqMarketRule(marketRuleId)
        except Exception as exc:
            raise ProviderUnavailableError(
                "IBKR reqMarketRule failed before economic write.",
                provider=IBKR_PROVIDER_KEY,
                operation="reqMarketRule",
            ) from exc


class IBKRMarketRuleResolver:
    """Resolve, cache, and validate dynamic IBKR price increment rules."""

    def __init__(self, client: IBKRMarketRuleClient) -> None:
        self._client = client
        self._cache: dict[int, IBKRMarketRule] = {}

    def resolve(
        self,
        *,
        market_rule_id: int,
    ) -> IBKRMarketRuleResolution:
        if type(market_rule_id) is not int or market_rule_id <= 0:
            raise IBKRMarketRuleError(
                "market_rule_id must be a positive int."
            )
        cached = self._cache.get(market_rule_id)
        if cached is not None:
            return IBKRMarketRuleResolution(
                rule=cached,
                cache_hit=True,
                provider_increment_count=0,
            )

        raw = self._client.reqMarketRule(market_rule_id)
        rule = normalize_ibkr_market_rule(
            market_rule_id=market_rule_id,
            raw_increments=raw,
        )
        self._cache[market_rule_id] = rule
        return IBKRMarketRuleResolution(
            rule=rule,
            cache_hit=False,
            provider_increment_count=len(rule.increments),
        )

    def validate_limit_price(
        self,
        *,
        instrument: IBKRInstrumentMappingResult,
        price: Decimal,
    ) -> IBKRMarketRuleValidationEvidence:
        if not isinstance(instrument, IBKRInstrumentMappingResult):
            raise IBKRMarketRuleError(
                "instrument must be an IBKRInstrumentMappingResult."
            )
        normalized_price = _positive_decimal(price, field_name="price")
        rule_id = ibkr_routing_market_rule_id(instrument)
        resolution = self.resolve(market_rule_id=rule_id)
        active = resolution.rule.active_increment(normalized_price)
        valid = resolution.rule.validates(normalized_price)
        return IBKRMarketRuleValidationEvidence(
            routing_exchange=instrument.routing_exchange,
            market_rule_id=rule_id,
            price=normalized_price,
            low_edge=active.low_edge,
            increment=active.increment,
            valid=valid,
            cache_hit=resolution.cache_hit,
        )


def ibkr_routing_market_rule_id(
    instrument: IBKRInstrumentMappingResult,
) -> int:
    """Return the market rule aligned to the qualified routing exchange."""

    if not isinstance(instrument, IBKRInstrumentMappingResult):
        raise IBKRMarketRuleError(
            "instrument must be an IBKRInstrumentMappingResult."
        )
    if not instrument.valid_exchanges or not instrument.market_rule_ids:
        raise ProviderProtocolError(
            "IBKR dynamic price validation lacks aligned market-rule metadata.",
            provider=IBKR_PROVIDER_KEY,
            operation="market_rule",
        )
    if len(instrument.valid_exchanges) != len(instrument.market_rule_ids):
        raise ProviderProtocolError(
            "IBKR valid exchanges and market rule IDs lost positional alignment.",
            provider=IBKR_PROVIDER_KEY,
            operation="market_rule",
        )

    matches = [
        index
        for index, exchange in enumerate(instrument.valid_exchanges)
        if exchange.upper() == instrument.routing_exchange.upper()
    ]
    if len(matches) != 1:
        raise ProviderProtocolError(
            "IBKR routing exchange does not map to exactly one market rule.",
            provider=IBKR_PROVIDER_KEY,
            operation="market_rule",
        )
    rule_id = instrument.market_rule_ids[matches[0]]
    if rule_id is None or rule_id <= 0:
        raise ProviderProtocolError(
            "IBKR routing exchange has no usable market rule ID.",
            provider=IBKR_PROVIDER_KEY,
            operation="market_rule",
        )
    return rule_id


def normalize_ibkr_market_rule(
    *,
    market_rule_id: int,
    raw_increments: object,
) -> IBKRMarketRule:
    """Normalize provider PriceIncrement values without float leakage."""

    if type(market_rule_id) is not int or market_rule_id <= 0:
        raise IBKRMarketRuleError(
            "market_rule_id must be a positive int."
        )
    if not isinstance(raw_increments, (list, tuple)):
        raise ProviderProtocolError(
            "IBKR reqMarketRule returned an unexpected payload type.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        )
    if not raw_increments:
        raise ProviderProtocolError(
            "IBKR reqMarketRule returned no price increments.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        )

    normalized: list[IBKRPriceIncrement] = []
    for raw in raw_increments:
        if not hasattr(raw, "lowEdge") or not hasattr(raw, "increment"):
            raise ProviderProtocolError(
                "IBKR market-rule increment payload is incomplete.",
                provider=IBKR_PROVIDER_KEY,
                operation="reqMarketRule",
            )
        low_edge = _provider_decimal(
            getattr(raw, "lowEdge"),
            field_name="lowEdge",
            allow_zero=True,
        )
        increment = _provider_decimal(
            getattr(raw, "increment"),
            field_name="increment",
            allow_zero=False,
        )
        normalized.append(
            IBKRPriceIncrement(
                low_edge=low_edge,
                increment=increment,
            )
        )

    try:
        return IBKRMarketRule(
            market_rule_id=market_rule_id,
            increments=tuple(normalized),
        )
    except IBKRMarketRuleError as exc:
        raise ProviderProtocolError(
            "IBKR reqMarketRule returned an invalid increment schedule.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        ) from exc


def build_ibkr_market_rule_resolver(
    connection: IBKRPaperConnectionRuntime,
) -> IBKRMarketRuleResolver:
    """Build dynamic market-rule resolution over the started PAPER runtime."""

    return IBKRMarketRuleResolver(
        IBKRRuntimeMarketRuleClient(connection),
    )


def _positive_decimal(value: Decimal, *, field_name: str) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value <= 0
    ):
        raise IBKRMarketRuleError(
            f"{field_name} must be a finite positive Decimal."
        )
    return value


def _provider_decimal(
    value: object,
    *,
    field_name: str,
    allow_zero: bool,
) -> Decimal:
    if isinstance(value, bool):
        raise ProviderProtocolError(
            f"IBKR {field_name} must be numeric.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        )
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, float):
        if not isfinite(value):
            raise ProviderProtocolError(
                f"IBKR {field_name} must be finite.",
                provider=IBKR_PROVIDER_KEY,
                operation="reqMarketRule",
            )
        decimal_value = Decimal(str(value))
    else:
        raise ProviderProtocolError(
            f"IBKR {field_name} must be numeric.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        )

    if not decimal_value.is_finite():
        raise ProviderProtocolError(
            f"IBKR {field_name} must be finite.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        )
    if allow_zero:
        valid = decimal_value >= 0
    else:
        valid = decimal_value > 0
    if not valid:
        raise ProviderProtocolError(
            f"IBKR {field_name} is outside the qualified numeric range.",
            provider=IBKR_PROVIDER_KEY,
            operation="reqMarketRule",
        )
    return decimal_value
