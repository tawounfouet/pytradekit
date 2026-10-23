"""IBKR contract qualification and runtime reference resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib import import_module
from typing import Protocol, cast

from pytradekit.brokers import ProviderProtocolError, ProviderUnavailableError
from pytradekit.shared import InstrumentId

from .contract_mapping import (
    IBKRContractDetailsRecord,
    IBKRContractMappingError,
    IBKRContractRecord,
    IBKRInstrumentMappingResult,
    IBKRPriceIncrementMode,
    IBKRSecurityType,
    map_ibkr_stock_contract,
)
from .discovery import IBKR_PROVIDER_KEY
from .identities import IBKRContractId
from .runtime import IBKRPaperConnectionRuntime

IBKR_CONTRACT_REFERENCE_VERSION = "0.8.0b4-lot06.3"


class IBKRContractResolutionError(ValueError):
    """Raised when provider reference data cannot be normalized safely."""


class IBKRContractDetailsClient(Protocol):
    """Provider-local client surface required by contract resolution."""

    def reqContractDetails(self, contract: object) -> list[object]:
        """Return all provider contract details matching the request."""

        ...


class IBKRContractRequestFactory(Protocol):
    """Create a provider-local contract request without leaking SDK types."""

    def build(self, *, contract_id: IBKRContractId) -> object:
        """Build one conId-based provider request."""

        ...


class IBKRCanonicalInstrumentIdResolver(Protocol):
    """Resolve canonical InstrumentId before provider mapping is emitted."""

    def resolve_instrument_id(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> InstrumentId | None:
        """Return the canonical instrument identity or None."""

        ...


class _ContractLike(Protocol):
    conId: int
    symbol: str
    secType: str
    exchange: str
    primaryExchange: str
    currency: str
    localSymbol: str
    tradingClass: str


class _ContractDetailsLike(Protocol):
    contract: object | None
    minTick: object
    minSize: object
    sizeIncrement: object
    suggestedSizeIncrement: object
    validExchanges: str
    marketRuleIds: str
    orderTypes: str
    timeZoneId: str
    stockType: str


class _ContractConstructor(Protocol):
    def __call__(self, **kwargs: object) -> object:
        ...


@dataclass(frozen=True, slots=True)
class IBKRContractResolutionEvidence:
    """Sanitized evidence for one provider reference lookup."""

    contract_id: IBKRContractId
    requested_symbol: str
    provider_match_count: int
    exact_match_count: int
    resolved: bool
    canonical_instrument_id: InstrumentId | None
    cache_hit: bool = False
    valid_exchanges: tuple[str, ...] = ()
    market_rule_ids: tuple[int | None, ...] = ()
    price_increment_mode: IBKRPriceIncrementMode | None = None

    def __post_init__(self) -> None:
        symbol = self.requested_symbol.strip()
        if not symbol:
            raise IBKRContractResolutionError(
                "requested_symbol must be non-empty."
            )
        object.__setattr__(self, "requested_symbol", symbol)

        for field_name in ("provider_match_count", "exact_match_count"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise IBKRContractResolutionError(
                    f"{field_name} must be a non-negative int."
                )
        if self.exact_match_count > self.provider_match_count:
            raise IBKRContractResolutionError(
                "exact_match_count cannot exceed provider_match_count."
            )
        if type(self.resolved) is not bool:
            raise IBKRContractResolutionError("resolved must be a bool.")
        if type(self.cache_hit) is not bool:
            raise IBKRContractResolutionError("cache_hit must be a bool.")


class StaticIBKRCanonicalInstrumentIdResolver:
    """Resolve canonical IDs from explicit conId and symbol bindings."""

    def __init__(
        self,
        bindings: Mapping[tuple[int, str], InstrumentId],
    ) -> None:
        self._bindings: dict[tuple[int, str], InstrumentId] = {}
        for raw_key, instrument_id in bindings.items():
            if (
                not isinstance(raw_key, tuple)
                or len(raw_key) != 2
                or type(raw_key[0]) is not int
                or not isinstance(raw_key[1], str)
            ):
                raise IBKRContractResolutionError(
                    "bindings keys must be (conId, symbol) tuples."
                )
            con_id, symbol = raw_key
            if con_id <= 0:
                raise IBKRContractResolutionError(
                    "bindings conId values must be positive."
                )
            normalized_symbol = symbol.strip()
            if not normalized_symbol:
                raise IBKRContractResolutionError(
                    "bindings symbols must be non-empty."
                )
            if not isinstance(instrument_id, InstrumentId):
                raise IBKRContractResolutionError(
                    "bindings values must be InstrumentId instances."
                )
            key = (con_id, normalized_symbol)
            if key in self._bindings:
                raise IBKRContractResolutionError(
                    "bindings must be unique by conId and symbol."
                )
            self._bindings[key] = instrument_id

    def resolve_instrument_id(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> InstrumentId | None:
        return self._bindings.get(
            (contract_id.value, _required_text(symbol, field_name="symbol"))
        )


class IBAsyncContractRequestFactory:
    """Create ib_async Contract requests through a dynamic provider boundary."""

    def __init__(
        self,
        *,
        constructor: _ContractConstructor | None = None,
    ) -> None:
        self._constructor = constructor

    def build(self, *, contract_id: IBKRContractId) -> object:
        if not isinstance(contract_id, IBKRContractId):
            raise IBKRContractResolutionError(
                "contract_id must be an IBKRContractId."
            )

        constructor = self._constructor or self._load_constructor()
        try:
            return constructor(
                conId=contract_id.value,
                exchange="SMART",
            )
        except Exception as exc:
            raise IBKRContractResolutionError(
                "ib_async Contract request construction failed."
            ) from exc

    @staticmethod
    def _load_constructor() -> _ContractConstructor:
        try:
            module = import_module("ib_async")
            constructor = module.Contract
        except (ImportError, AttributeError) as exc:
            raise IBKRContractResolutionError(
                "ib_async Contract is unavailable."
            ) from exc
        return cast(_ContractConstructor, constructor)


class IBKRRuntimeContractDetailsClient:
    """Proxy contract-detail requests through a started PAPER connection."""

    def __init__(self, connection: IBKRPaperConnectionRuntime) -> None:
        if not isinstance(connection, IBKRPaperConnectionRuntime):
            raise IBKRContractResolutionError(
                "connection must be an IBKRPaperConnectionRuntime."
            )
        self._connection = connection

    def reqContractDetails(self, contract: object) -> list[object]:
        client = self._connection.read_client()
        if not hasattr(client, "reqContractDetails"):
            raise ProviderUnavailableError(
                "IBKR PAPER client has no contract-details capability.",
                provider=IBKR_PROVIDER_KEY,
                operation="contract_details",
            )
        provider_client = cast(IBKRContractDetailsClient, client)
        try:
            return list(provider_client.reqContractDetails(contract))
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(
                "IBKR contract-details request failed "
                f"({type(exc).__name__}).",
                provider=IBKR_PROVIDER_KEY,
                operation="contract_details",
            ) from exc


class IBKRContractReferenceResolver:
    """Resolve conId-based provider reference data into canonical mappings."""

    def __init__(
        self,
        *,
        client: IBKRContractDetailsClient,
        instrument_ids: IBKRCanonicalInstrumentIdResolver,
        request_factory: IBKRContractRequestFactory | None = None,
    ) -> None:
        self._client = client
        self._instrument_ids = instrument_ids
        self._request_factory = request_factory or IBAsyncContractRequestFactory()
        self._cache: dict[
            tuple[int, str],
            IBKRInstrumentMappingResult,
        ] = {}
        self._last_evidence: IBKRContractResolutionEvidence | None = None

    @property
    def last_evidence(self) -> IBKRContractResolutionEvidence | None:
        return self._last_evidence

    def resolve(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> IBKRInstrumentMappingResult | None:
        if not isinstance(contract_id, IBKRContractId):
            raise IBKRContractResolutionError(
                "contract_id must be an IBKRContractId."
            )
        normalized_symbol = _required_text(
            symbol,
            field_name="symbol",
        )
        cache_key = (contract_id.value, normalized_symbol)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._last_evidence = _evidence_from_mapping(
                contract_id=contract_id,
                symbol=normalized_symbol,
                provider_match_count=0,
                exact_match_count=0,
                mapping=cached,
                cache_hit=True,
            )
            return cached

        instrument_id = self._instrument_ids.resolve_instrument_id(
            contract_id=contract_id,
            symbol=normalized_symbol,
        )
        if instrument_id is None:
            self._last_evidence = IBKRContractResolutionEvidence(
                contract_id=contract_id,
                requested_symbol=normalized_symbol,
                provider_match_count=0,
                exact_match_count=0,
                resolved=False,
                canonical_instrument_id=None,
            )
            return None

        request = self._request_factory.build(contract_id=contract_id)
        try:
            raw_matches = list(self._client.reqContractDetails(request))
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(
                "IBKR contract-details request failed "
                f"({type(exc).__name__}).",
                provider=IBKR_PROVIDER_KEY,
                operation="contract_details",
            ) from exc

        if not raw_matches:
            self._last_evidence = IBKRContractResolutionEvidence(
                contract_id=contract_id,
                requested_symbol=normalized_symbol,
                provider_match_count=0,
                exact_match_count=0,
                resolved=False,
                canonical_instrument_id=instrument_id,
            )
            return None

        try:
            normalized_matches = tuple(
                normalize_ibkr_contract_details(item)
                for item in raw_matches
            )
        except IBKRContractResolutionError as exc:
            raise ProviderProtocolError(
                "IBKR contract-details payload could not be normalized safely.",
                provider=IBKR_PROVIDER_KEY,
                operation="contract_details",
            ) from exc
        exact = tuple(
            details
            for details in normalized_matches
            if (
                details.contract.contract_id == contract_id
                and details.contract.symbol == normalized_symbol
            )
        )

        if len(exact) != 1:
            self._last_evidence = IBKRContractResolutionEvidence(
                contract_id=contract_id,
                requested_symbol=normalized_symbol,
                provider_match_count=len(normalized_matches),
                exact_match_count=len(exact),
                resolved=False,
                canonical_instrument_id=instrument_id,
            )
            raise ProviderProtocolError(
                "IBKR contract lookup did not produce exactly one exact "
                "conId and symbol match.",
                provider=IBKR_PROVIDER_KEY,
                operation="contract_details",
            )

        try:
            mapping = map_ibkr_stock_contract(
                exact[0],
                instrument_id=instrument_id,
            )
        except IBKRContractMappingError as exc:
            raise ProviderProtocolError(
                "IBKR contract details violate the qualified reference "
                "mapping contract.",
                provider=IBKR_PROVIDER_KEY,
                operation="contract_details",
            ) from exc

        self._cache[cache_key] = mapping
        self._last_evidence = _evidence_from_mapping(
            contract_id=contract_id,
            symbol=normalized_symbol,
            provider_match_count=len(normalized_matches),
            exact_match_count=1,
            mapping=mapping,
        )
        return mapping

    def prime(
        self,
        mappings: Iterable[IBKRInstrumentMappingResult],
    ) -> None:
        """Prime only previously qualified mappings into the runtime cache."""

        for mapping in mappings:
            if not isinstance(mapping, IBKRInstrumentMappingResult):
                raise IBKRContractResolutionError(
                    "prime mappings must be IBKRInstrumentMappingResult values."
                )
            key = (
                int(mapping.identity.external_id),
                mapping.identity.external_symbol,
            )
            existing = self._cache.get(key)
            if existing is not None and existing != mapping:
                raise IBKRContractResolutionError(
                    "contract reference cache cannot silently rebind a mapping."
                )
            self._cache[key] = mapping


def build_ibkr_contract_reference_resolver(
    *,
    connection: IBKRPaperConnectionRuntime,
    instrument_ids: IBKRCanonicalInstrumentIdResolver,
    request_factory: IBKRContractRequestFactory | None = None,
) -> IBKRContractReferenceResolver:
    """Compose LOT-06.3 over a started IBKR PAPER connection."""

    return IBKRContractReferenceResolver(
        client=IBKRRuntimeContractDetailsClient(connection),
        instrument_ids=instrument_ids,
        request_factory=request_factory,
    )


def normalize_ibkr_contract_details(
    raw: object,
) -> IBKRContractDetailsRecord:
    """Normalize one ib_async ContractDetails object into LOT-05.2 records."""

    details = _contract_details(raw)
    contract = _contract(details.contract)

    try:
        security_type = IBKRSecurityType(contract.secType.strip().upper())
    except ValueError as exc:
        raise IBKRContractResolutionError(
            "IBKR contract security type is outside the qualified scope."
        ) from exc

    valid_exchanges = _csv_labels(details.validExchanges)
    market_rule_ids = _market_rule_ids(details.marketRuleIds)

    try:
        return IBKRContractDetailsRecord(
            contract=IBKRContractRecord(
                contract_id=IBKRContractId(contract.conId),
                symbol=_required_text(
                    contract.symbol,
                    field_name="contract.symbol",
                ),
                security_type=security_type,
                exchange=_required_text(
                    contract.exchange,
                    field_name="contract.exchange",
                ),
                primary_exchange=_required_text(
                    contract.primaryExchange,
                    field_name="contract.primaryExchange",
                ),
                currency=_required_text(
                    contract.currency,
                    field_name="contract.currency",
                ),
                local_symbol=_required_text(
                    contract.localSymbol,
                    field_name="contract.localSymbol",
                ),
                trading_class=_optional_text(contract.tradingClass),
            ),
            min_tick=_positive_provider_decimal(
                details.minTick,
                field_name="ContractDetails.minTick",
            ),
            min_size=_positive_provider_decimal(
                details.minSize,
                field_name="ContractDetails.minSize",
            ),
            size_increment=_positive_provider_decimal(
                details.sizeIncrement,
                field_name="ContractDetails.sizeIncrement",
            ),
            suggested_size_increment=_positive_provider_decimal(
                details.suggestedSizeIncrement,
                field_name="ContractDetails.suggestedSizeIncrement",
            ),
            valid_exchanges=valid_exchanges,
            market_rule_ids=market_rule_ids,
            order_types=_csv_labels(details.orderTypes),
            time_zone_id=_optional_text(details.timeZoneId),
            stock_type=_optional_text(details.stockType),
        )
    except (IBKRContractMappingError, ValueError) as exc:
        raise IBKRContractResolutionError(
            "IBKR ContractDetails could not be normalized safely."
        ) from exc


def _contract_details(value: object) -> _ContractDetailsLike:
    required = (
        "contract",
        "minTick",
        "minSize",
        "sizeIncrement",
        "suggestedSizeIncrement",
        "validExchanges",
        "marketRuleIds",
        "orderTypes",
        "timeZoneId",
        "stockType",
    )
    if any(not hasattr(value, field) for field in required):
        raise IBKRContractResolutionError(
            "IBKR ContractDetails object has an invalid shape."
        )
    return cast(_ContractDetailsLike, value)


def _contract(value: object | None) -> _ContractLike:
    if value is None:
        raise IBKRContractResolutionError(
            "IBKR ContractDetails.contract is unavailable."
        )
    required = (
        "conId",
        "symbol",
        "secType",
        "exchange",
        "primaryExchange",
        "currency",
        "localSymbol",
        "tradingClass",
    )
    if any(not hasattr(value, field) for field in required):
        raise IBKRContractResolutionError(
            "IBKR qualified Contract object has an invalid shape."
        )
    return cast(_ContractLike, value)


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRContractResolutionError(
            f"{field_name} must be a string."
        )
    normalized = value.strip()
    if not normalized:
        raise IBKRContractResolutionError(
            f"{field_name} must be non-empty."
        )
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise IBKRContractResolutionError(
            "optional provider text must be a string or None."
        )
    normalized = value.strip()
    return normalized or None


def _csv_labels(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, str):
        raise IBKRContractResolutionError(
            "provider comma-separated labels must be a string."
        )
    if not value.strip():
        return ()
    return tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )


def _market_rule_ids(value: object) -> tuple[int | None, ...]:
    if value is None:
        return ()
    if not isinstance(value, str):
        raise IBKRContractResolutionError(
            "marketRuleIds must be a string."
        )
    if not value.strip():
        return ()

    result: list[int | None] = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            result.append(None)
            continue
        try:
            rule_id = int(item)
        except ValueError as exc:
            raise IBKRContractResolutionError(
                "marketRuleIds contains a non-integer value."
            ) from exc
        if rule_id < 0:
            raise IBKRContractResolutionError(
                "marketRuleIds cannot contain negative values."
            )
        result.append(rule_id)
    return tuple(result)


def _positive_provider_decimal(
    value: object,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise IBKRContractResolutionError(
            f"{field_name} is not numeric."
        ) from exc
    if not parsed.is_finite():
        raise IBKRContractResolutionError(
            f"{field_name} must be finite."
        )
    if parsed < 0:
        raise IBKRContractResolutionError(
            f"{field_name} cannot be negative."
        )
    if parsed == 0:
        return None
    return parsed


def _evidence_from_mapping(
    *,
    contract_id: IBKRContractId,
    symbol: str,
    provider_match_count: int,
    exact_match_count: int,
    mapping: IBKRInstrumentMappingResult,
    cache_hit: bool = False,
) -> IBKRContractResolutionEvidence:
    return IBKRContractResolutionEvidence(
        contract_id=contract_id,
        requested_symbol=symbol,
        provider_match_count=provider_match_count,
        exact_match_count=exact_match_count,
        resolved=True,
        canonical_instrument_id=mapping.instrument.id,
        cache_hit=cache_hit,
        valid_exchanges=mapping.valid_exchanges,
        market_rule_ids=mapping.market_rule_ids,
        price_increment_mode=mapping.price_increment_mode,
    )
