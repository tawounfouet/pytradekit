"""IBKR SDK-free execution details and canonical Fill mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderStateReconciliationRequired,
)
from pytradekit.execution import ExecutionReport, ExecutionStatus, Fill, FillId
from pytradekit.orders.domain import OrderSide
from pytradekit.shared import Price, Quantity, require_utc_datetime

from .contract_mapping import IBKRInstrumentMappingResult
from .discovery import IBKR_PROVIDER_KEY
from .identities import (
    IBKRClientId,
    IBKRContractId,
    IBKRExecutionId,
    IBKRExecutionIdentity,
    IBKRIdentityError,
    IBKROrderIdentity,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)
from .identity_registry import IBKROrderIdentityRegistry

_UTC_EXECUTION_TIME = re.compile(r"^\d{8}-\d{2}:\d{2}:\d{2}$")
_ZONED_EXECUTION_TIME = re.compile(
    r"^(?P<date>\d{8})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<zone>\S+)$"
)


class IBKRExecutionMappingError(ValueError):
    """Raised when IBKR execution details violate the frozen mapping contract."""


class IBKRExecutionSide(StrEnum):
    """IBKR execution side values used by Execution.side."""

    BOUGHT = "BOT"
    SOLD = "SLD"


class IBKRExecutionDisposition(StrEnum):
    """Disposition of one execId observation inside the adapter."""

    NEW = "new"
    DUPLICATE = "duplicate"
    CORRECTION = "correction"


@dataclass(frozen=True, slots=True)
class IBKRExecutionRegistration:
    """Result of registering one provider execution identity."""

    disposition: IBKRExecutionDisposition
    execution_id: IBKRExecutionId
    previous_execution_id: IBKRExecutionId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, IBKRExecutionDisposition):
            raise IBKRExecutionMappingError(
                "disposition must be an IBKRExecutionDisposition."
            )
        if not isinstance(self.execution_id, IBKRExecutionId):
            raise IBKRExecutionMappingError(
                "execution_id must be an IBKRExecutionId."
            )
        if self.disposition is IBKRExecutionDisposition.CORRECTION:
            if self.previous_execution_id is None:
                raise IBKRExecutionMappingError(
                    "Correction registration requires previous_execution_id."
                )
            if not self.execution_id.can_be_correction_of(
                self.previous_execution_id
            ):
                raise IBKRExecutionMappingError(
                    "Correction registration must preserve the execId family."
                )
        elif self.previous_execution_id is not None:
            raise IBKRExecutionMappingError(
                "Only correction registration may declare previous_execution_id."
            )


class IBKRExecutionRegistry:
    """Prevent duplicate effects and surface execution corrections explicitly."""

    def __init__(self) -> None:
        self._accepted_ids: set[str] = set()
        self._first_by_family: dict[str, IBKRExecutionId] = {}
        self._correction_ids: set[str] = set()

    def register(
        self,
        execution_id: IBKRExecutionId,
    ) -> IBKRExecutionRegistration:
        """Classify one execId as new, duplicate, or correction."""

        if not isinstance(execution_id, IBKRExecutionId):
            raise IBKRExecutionMappingError(
                "execution_id must be an IBKRExecutionId."
            )

        raw = execution_id.value
        if raw in self._correction_ids:
            family = execution_id.correction_family
            previous = (
                self._first_by_family.get(family)
                if family is not None
                else None
            )
            if previous is None:
                raise IBKRExecutionMappingError(
                    "Correction registry lost its original execution identity."
                )
            return IBKRExecutionRegistration(
                disposition=IBKRExecutionDisposition.CORRECTION,
                execution_id=execution_id,
                previous_execution_id=previous,
            )

        if raw in self._accepted_ids:
            return IBKRExecutionRegistration(
                disposition=IBKRExecutionDisposition.DUPLICATE,
                execution_id=execution_id,
            )

        family = execution_id.correction_family
        if family is not None:
            previous = self._first_by_family.get(family)
            if previous is not None and previous != execution_id:
                self._correction_ids.add(raw)
                return IBKRExecutionRegistration(
                    disposition=IBKRExecutionDisposition.CORRECTION,
                    execution_id=execution_id,
                    previous_execution_id=previous,
                )
            self._first_by_family[family] = execution_id

        self._accepted_ids.add(raw)
        return IBKRExecutionRegistration(
            disposition=IBKRExecutionDisposition.NEW,
            execution_id=execution_id,
        )

    def __len__(self) -> int:
        return len(self._accepted_ids)


@dataclass(frozen=True, slots=True)
class IBKRExecutionDetailsObservation:
    """SDK-free execution observation derived from execDetails."""

    contract_id: IBKRContractId
    symbol: str
    execution_id: IBKRExecutionId
    client_id: IBKRClientId
    session_order_id: IBKRSessionOrderId
    permanent_order_id: IBKRPermanentOrderId
    order_reference: IBKROrderReference
    side: IBKRExecutionSide
    shares: Decimal
    price: Decimal
    cumulative_quantity: Decimal
    average_price: Decimal
    exchange: str
    account: str
    occurred_at: datetime
    pending_price_revision: bool = False

    def __post_init__(self) -> None:
        expected_types = (
            ("contract_id", self.contract_id, IBKRContractId),
            ("execution_id", self.execution_id, IBKRExecutionId),
            ("client_id", self.client_id, IBKRClientId),
            ("session_order_id", self.session_order_id, IBKRSessionOrderId),
            ("permanent_order_id", self.permanent_order_id, IBKRPermanentOrderId),
            ("order_reference", self.order_reference, IBKROrderReference),
            ("side", self.side, IBKRExecutionSide),
        )
        for field_name, value, expected_type in expected_types:
            if not isinstance(value, expected_type):
                raise IBKRExecutionMappingError(
                    f"{field_name} has an invalid type."
                )

        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )
        object.__setattr__(
            self,
            "exchange",
            _required_text(self.exchange, field_name="exchange"),
        )
        object.__setattr__(
            self,
            "account",
            _required_text(self.account, field_name="account"),
        )
        object.__setattr__(
            self,
            "shares",
            _positive_decimal(self.shares, field_name="shares"),
        )
        object.__setattr__(
            self,
            "price",
            _positive_decimal(self.price, field_name="price"),
        )
        object.__setattr__(
            self,
            "cumulative_quantity",
            _positive_decimal(
                self.cumulative_quantity,
                field_name="cumulative_quantity",
            ),
        )
        object.__setattr__(
            self,
            "average_price",
            _positive_decimal(
                self.average_price,
                field_name="average_price",
            ),
        )
        if self.cumulative_quantity < self.shares:
            raise IBKRExecutionMappingError(
                "cumulative_quantity must be greater than or equal to shares."
            )
        object.__setattr__(
            self,
            "occurred_at",
            require_utc_datetime(
                self.occurred_at,
                field_name="execDetails occurred_at",
            ),
        )
        if type(self.pending_price_revision) is not bool:
            raise IBKRExecutionMappingError(
                "pending_price_revision must be a bool."
            )


def parse_ibkr_execution_time(value: str) -> datetime:
    """Parse explicit IBKR execution time into UTC without timezone relabeling."""

    raw = _required_text(value, field_name="execution time")

    if _UTC_EXECUTION_TIME.fullmatch(raw):
        parsed = datetime.strptime(raw, "%Y%m%d-%H:%M:%S")
        return parsed.replace(tzinfo=UTC)

    match = _ZONED_EXECUTION_TIME.fullmatch(raw)
    if match is None:
        raise IBKRExecutionMappingError(
            "IBKR execution time must include an explicit IANA timezone "
            "or use the documented UTC YYYYMMDD-HH:MM:SS form."
        )

    local_naive = datetime.strptime(
        f"{match.group('date')} {match.group('time')}",
        "%Y%m%d %H:%M:%S",
    )
    zone_name = match.group("zone")
    try:
        zone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError as exc:
        raise IBKRExecutionMappingError(
            f"Unknown IBKR execution timezone {zone_name!r}."
        ) from exc

    first = local_naive.replace(tzinfo=zone, fold=0)
    second = local_naive.replace(tzinfo=zone, fold=1)
    first_round_trip = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    second_round_trip = second.astimezone(UTC).astimezone(zone).replace(tzinfo=None)

    if (
        first.utcoffset() != second.utcoffset()
        and first_round_trip == local_naive
        and second_round_trip == local_naive
    ):
        raise IBKRExecutionMappingError(
            "IBKR execution time is ambiguous across a timezone fold."
        )
    if first_round_trip != local_naive:
        raise IBKRExecutionMappingError(
            "IBKR execution time is invalid in the supplied timezone."
        )

    return first.astimezone(UTC)


def map_ibkr_execution_report(
    observation: IBKRExecutionDetailsObservation,
    *,
    context: ProviderExecutionContext,
    expected_side: OrderSide,
    expected_quantity: Quantity,
    instrument: IBKRInstrumentMappingResult,
    order_registry: IBKROrderIdentityRegistry,
    execution_registry: IBKRExecutionRegistry,
) -> ExecutionReport | None:
    """Map one execDetails observation to one idempotent canonical Fill fact."""

    _validate_mapping_inputs(
        observation=observation,
        context=context,
        expected_side=expected_side,
        expected_quantity=expected_quantity,
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )

    if observation.pending_price_revision:
        raise _reconciliation_required(
            "IBKR execution price revision is pending."
        )

    _validate_execution_contract(
        observation,
        context=context,
        expected_side=expected_side,
        expected_quantity=expected_quantity,
        instrument=instrument,
    )

    order_identity = _ensure_execution_order_identity(
        observation,
        context=context,
        registry=order_registry,
    )

    registration = execution_registry.register(observation.execution_id)
    if registration.disposition is IBKRExecutionDisposition.DUPLICATE:
        return None
    if registration.disposition is IBKRExecutionDisposition.CORRECTION:
        raise _reconciliation_required(
            "IBKR execution correction detected; do not emit a second "
            "canonical economic Fill."
        )

    execution_identity = IBKRExecutionIdentity(
        execution_id=observation.execution_id,
        permanent_order_id=observation.permanent_order_id,
        session_order_id=observation.session_order_id,
        client_id=observation.client_id,
        order_reference=observation.order_reference,
    )
    provider_fill_identity = execution_identity.to_provider_identity()

    fill = Fill(
        id=_canonical_fill_id(provider_fill_identity.external_fill_id),
        order_id=context.order_id,
        quantity=Quantity(observation.shares),
        price=Price(observation.price, context.quote_currency),
        occurred_at=observation.occurred_at,
        external_fill_id=provider_fill_identity.external_fill_id,
        fee=None,
    )

    status = (
        ExecutionStatus.FILLED
        if observation.cumulative_quantity == expected_quantity.value
        else ExecutionStatus.PARTIALLY_FILLED
    )

    provider_order_identity = order_identity.to_provider_identity()
    return ExecutionReport(
        order_id=context.order_id,
        status=status,
        occurred_at=observation.occurred_at,
        correlation_id=context.correlation_id,
        external_order_id=provider_order_identity.external_order_id,
        fill=fill,
    )


def _validate_mapping_inputs(
    *,
    observation: IBKRExecutionDetailsObservation,
    context: ProviderExecutionContext,
    expected_side: OrderSide,
    expected_quantity: Quantity,
    instrument: IBKRInstrumentMappingResult,
    order_registry: IBKROrderIdentityRegistry,
    execution_registry: IBKRExecutionRegistry,
) -> None:
    if not isinstance(observation, IBKRExecutionDetailsObservation):
        raise IBKRExecutionMappingError(
            "observation must be an IBKRExecutionDetailsObservation."
        )
    if not isinstance(context, ProviderExecutionContext):
        raise IBKRExecutionMappingError(
            "context must be a ProviderExecutionContext."
        )
    if not isinstance(expected_side, OrderSide):
        raise IBKRExecutionMappingError("expected_side must be an OrderSide.")
    if (
        not isinstance(expected_quantity, Quantity)
        or expected_quantity.value <= 0
    ):
        raise IBKRExecutionMappingError(
            "expected_quantity must be a strictly positive Quantity."
        )
    if not isinstance(instrument, IBKRInstrumentMappingResult):
        raise IBKRExecutionMappingError(
            "instrument must be an IBKRInstrumentMappingResult."
        )
    if not isinstance(order_registry, IBKROrderIdentityRegistry):
        raise IBKRExecutionMappingError(
            "order_registry must be an IBKROrderIdentityRegistry."
        )
    if not isinstance(execution_registry, IBKRExecutionRegistry):
        raise IBKRExecutionMappingError(
            "execution_registry must be an IBKRExecutionRegistry."
        )


def _validate_execution_contract(
    observation: IBKRExecutionDetailsObservation,
    *,
    context: ProviderExecutionContext,
    expected_side: OrderSide,
    expected_quantity: Quantity,
    instrument: IBKRInstrumentMappingResult,
) -> None:
    if observation.order_reference.value != context.client_order_reference:
        raise _protocol_error(
            "IBKR execDetails orderRef does not match canonical order context."
        )
    if str(observation.contract_id) != instrument.identity.external_id:
        raise _protocol_error(
            "IBKR execDetails conId does not match resolved provider instrument."
        )
    if observation.symbol != instrument.identity.external_symbol:
        raise _protocol_error(
            "IBKR execDetails symbol does not match resolved provider instrument."
        )
    if context.quote_currency != instrument.instrument.quote_currency:
        raise _protocol_error(
            "IBKR execution currency does not match canonical execution context."
        )

    provider_side = (
        OrderSide.BUY
        if observation.side is IBKRExecutionSide.BOUGHT
        else OrderSide.SELL
    )
    if provider_side is not expected_side:
        raise _protocol_error(
            "IBKR execDetails side does not match canonical order side."
        )

    if observation.cumulative_quantity > expected_quantity.value:
        raise _protocol_error(
            "IBKR cumulative execution quantity exceeds canonical order quantity."
        )


def _ensure_execution_order_identity(
    observation: IBKRExecutionDetailsObservation,
    *,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> IBKROrderIdentity:
    expected_reference = IBKROrderReference(context.client_order_reference)

    try:
        current = registry.find_by_routing_key(
            client_id=observation.client_id,
            session_order_id=observation.session_order_id,
        )
        if current is not None:
            if current.client_reference != expected_reference:
                raise _protocol_error(
                    "IBKR execution routing identity conflicts with canonical orderRef."
                )
            return registry.bind_permanent_order_id(
                client_id=observation.client_id,
                session_order_id=observation.session_order_id,
                permanent_order_id=observation.permanent_order_id,
            )

        durable = registry.find_by_permanent_order_id(
            observation.permanent_order_id
        )
        if durable is not None:
            if durable.client_reference != expected_reference:
                raise _protocol_error(
                    "IBKR execution permId conflicts with canonical orderRef."
                )
            return registry.register(
                IBKROrderIdentity(
                    client_id=observation.client_id,
                    session_order_id=observation.session_order_id,
                    client_reference=durable.client_reference,
                    permanent_order_id=observation.permanent_order_id,
                )
            )

        return registry.register(
            IBKROrderIdentity(
                client_id=observation.client_id,
                session_order_id=observation.session_order_id,
                client_reference=expected_reference,
                permanent_order_id=observation.permanent_order_id,
            )
        )
    except ProviderProtocolError:
        raise
    except IBKRIdentityError as exc:
        raise _protocol_error(
            "IBKR execution identity conflicts with previous provider evidence."
        ) from exc


def _canonical_fill_id(external_fill_id: str) -> FillId:
    return FillId(
        uuid5(
            NAMESPACE_URL,
            f"pytradekit:ibkr:fill:{external_fill_id}",
        )
    )


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRExecutionMappingError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKRExecutionMappingError(f"{field_name} must be non-empty.")
    return normalized


def _positive_decimal(value: object, *, field_name: str) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value <= 0
    ):
        raise IBKRExecutionMappingError(
            f"{field_name} must be a finite positive Decimal."
        )
    return value


def _protocol_error(message: str) -> ProviderProtocolError:
    return ProviderProtocolError(
        message,
        provider=IBKR_PROVIDER_KEY,
        operation="execution_details",
    )


def _reconciliation_required(
    message: str,
) -> ProviderStateReconciliationRequired:
    return ProviderStateReconciliationRequired(
        message,
        provider=IBKR_PROVIDER_KEY,
        operation="execution_details",
    )
