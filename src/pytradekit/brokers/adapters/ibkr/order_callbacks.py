"""IBKR SDK-free order callback observations and status normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderOrderStateSnapshot,
    ProviderProtocolError,
    ProviderStateReconciliationRequired,
)
from pytradekit.execution import ExecutionReport, ExecutionStatus
from pytradekit.shared import require_utc_datetime

from .discovery import IBKR_PROVIDER_KEY
from .identities import (
    IBKRClientId,
    IBKRIdentityError,
    IBKROrderIdentity,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)
from .identity_registry import IBKROrderIdentityRegistry

IBKR_ORDER_REJECTED_ERROR_CODE: Final = 201
IBKR_ORDER_CANCELLED_ERROR_CODE: Final = 202


class IBKROrderCallbackError(ValueError):
    """Raised when an IBKR callback observation violates the frozen contract."""


class IBKROrderStatus(StrEnum):
    """Known TWS order status values used by the frozen 0.8 scope."""

    PENDING_SUBMIT = "PendingSubmit"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    PENDING_CANCEL = "PendingCancel"
    API_CANCELLED = "ApiCancelled"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    INACTIVE = "Inactive"


class IBKROrderStateDisposition(StrEnum):
    """How one IBKR provider status must be handled."""

    MAP = "map"
    TRANSIENT = "transient"
    RECONCILE = "reconcile"


@dataclass(frozen=True, slots=True)
class IBKROrderStateRule:
    """Frozen handling rule for one provider order status."""

    disposition: IBKROrderStateDisposition
    canonical_status: ExecutionStatus | None = None

    def __post_init__(self) -> None:
        if self.disposition is IBKROrderStateDisposition.MAP:
            if self.canonical_status is None:
                raise IBKROrderCallbackError(
                    "Mapped IBKR status requires a canonical ExecutionStatus."
                )
            return
        if self.canonical_status is not None:
            raise IBKROrderCallbackError(
                "Non-mapped IBKR status must not declare a canonical status."
            )


IBKR_ORDER_STATUS_RULES: Final[Mapping[str, IBKROrderStateRule]] = MappingProxyType(
    {
        IBKROrderStatus.PENDING_SUBMIT.value: IBKROrderStateRule(
            IBKROrderStateDisposition.TRANSIENT
        ),
        IBKROrderStatus.PRE_SUBMITTED.value: IBKROrderStateRule(
            IBKROrderStateDisposition.MAP,
            ExecutionStatus.ACCEPTED,
        ),
        IBKROrderStatus.SUBMITTED.value: IBKROrderStateRule(
            IBKROrderStateDisposition.MAP,
            ExecutionStatus.ACCEPTED,
        ),
        IBKROrderStatus.PENDING_CANCEL.value: IBKROrderStateRule(
            IBKROrderStateDisposition.TRANSIENT
        ),
        IBKROrderStatus.API_CANCELLED.value: IBKROrderStateRule(
            IBKROrderStateDisposition.MAP,
            ExecutionStatus.CANCELLED,
        ),
        IBKROrderStatus.CANCELLED.value: IBKROrderStateRule(
            IBKROrderStateDisposition.MAP,
            ExecutionStatus.CANCELLED,
        ),
        IBKROrderStatus.FILLED.value: IBKROrderStateRule(
            IBKROrderStateDisposition.MAP,
            ExecutionStatus.FILLED,
        ),
        IBKROrderStatus.INACTIVE.value: IBKROrderStateRule(
            IBKROrderStateDisposition.RECONCILE
        ),
    }
)


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKROrderCallbackError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKROrderCallbackError(f"{field_name} must be non-empty.")
    return normalized


def _optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name=field_name)


def _non_negative_decimal(value: Decimal, *, field_name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise IBKROrderCallbackError(
            f"{field_name} must be a finite non-negative Decimal."
        )
    return value


def _optional_positive_decimal(
    value: Decimal | None,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise IBKROrderCallbackError(
            f"{field_name} must be a finite positive Decimal or None."
        )
    return value


@dataclass(frozen=True, slots=True)
class IBKROpenOrderObservation:
    """SDK-free observation derived from openOrder plus OrderState."""

    client_id: IBKRClientId
    session_order_id: IBKRSessionOrderId
    order_reference: IBKROrderReference
    permanent_order_id: IBKRPermanentOrderId | None
    provider_status: str
    reject_reason: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, IBKRClientId):
            raise IBKROrderCallbackError("client_id must be an IBKRClientId.")
        if not isinstance(self.session_order_id, IBKRSessionOrderId):
            raise IBKROrderCallbackError(
                "session_order_id must be an IBKRSessionOrderId."
            )
        if not isinstance(self.order_reference, IBKROrderReference):
            raise IBKROrderCallbackError(
                "order_reference must be an IBKROrderReference."
            )
        if self.permanent_order_id is not None and not isinstance(
            self.permanent_order_id,
            IBKRPermanentOrderId,
        ):
            raise IBKROrderCallbackError(
                "permanent_order_id must be an IBKRPermanentOrderId or None."
            )
        object.__setattr__(
            self,
            "provider_status",
            _text(self.provider_status, field_name="provider_status"),
        )
        object.__setattr__(
            self,
            "reject_reason",
            _optional_text(self.reject_reason, field_name="reject_reason"),
        )
        object.__setattr__(
            self,
            "observed_at",
            require_utc_datetime(self.observed_at, field_name="openOrder observed_at"),
        )


@dataclass(frozen=True, slots=True)
class IBKROrderStatusObservation:
    """SDK-free observation derived from the orderStatus callback."""

    client_id: IBKRClientId
    session_order_id: IBKRSessionOrderId
    permanent_order_id: IBKRPermanentOrderId | None
    provider_status: str
    filled: Decimal
    remaining: Decimal
    average_fill_price: Decimal | None
    last_fill_price: Decimal | None
    why_held: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, IBKRClientId):
            raise IBKROrderCallbackError("client_id must be an IBKRClientId.")
        if not isinstance(self.session_order_id, IBKRSessionOrderId):
            raise IBKROrderCallbackError(
                "session_order_id must be an IBKRSessionOrderId."
            )
        if self.permanent_order_id is not None and not isinstance(
            self.permanent_order_id,
            IBKRPermanentOrderId,
        ):
            raise IBKROrderCallbackError(
                "permanent_order_id must be an IBKRPermanentOrderId or None."
            )
        object.__setattr__(
            self,
            "provider_status",
            _text(self.provider_status, field_name="provider_status"),
        )
        object.__setattr__(
            self,
            "filled",
            _non_negative_decimal(self.filled, field_name="filled"),
        )
        object.__setattr__(
            self,
            "remaining",
            _non_negative_decimal(self.remaining, field_name="remaining"),
        )
        object.__setattr__(
            self,
            "average_fill_price",
            _optional_positive_decimal(
                self.average_fill_price,
                field_name="average_fill_price",
            ),
        )
        object.__setattr__(
            self,
            "last_fill_price",
            _optional_positive_decimal(
                self.last_fill_price,
                field_name="last_fill_price",
            ),
        )
        object.__setattr__(
            self,
            "why_held",
            _optional_text(self.why_held, field_name="why_held"),
        )
        object.__setattr__(
            self,
            "observed_at",
            require_utc_datetime(
                self.observed_at,
                field_name="orderStatus observed_at",
            ),
        )


@dataclass(frozen=True, slots=True)
class IBKROrderErrorObservation:
    """Order-scoped SDK-free observation derived from EWrapper.error."""

    client_id: IBKRClientId
    session_order_id: IBKRSessionOrderId
    error_code: int
    message: str
    advanced_order_reject_json: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, IBKRClientId):
            raise IBKROrderCallbackError("client_id must be an IBKRClientId.")
        if not isinstance(self.session_order_id, IBKRSessionOrderId):
            raise IBKROrderCallbackError(
                "session_order_id must be an IBKRSessionOrderId."
            )
        if type(self.error_code) is not int or self.error_code < 0:
            raise IBKROrderCallbackError(
                "error_code must be a non-negative integer."
            )
        object.__setattr__(
            self,
            "message",
            _text(self.message, field_name="message"),
        )
        object.__setattr__(
            self,
            "advanced_order_reject_json",
            _optional_text(
                self.advanced_order_reject_json,
                field_name="advanced_order_reject_json",
            ),
        )
        object.__setattr__(
            self,
            "observed_at",
            require_utc_datetime(self.observed_at, field_name="error observed_at"),
        )


def ibkr_order_status_rule(provider_status: str) -> IBKROrderStateRule:
    """Return the frozen handling rule, reconciling unknown provider statuses."""

    normalized = _text(provider_status, field_name="provider_status")
    return IBKR_ORDER_STATUS_RULES.get(
        normalized,
        IBKROrderStateRule(IBKROrderStateDisposition.RECONCILE),
    )


def register_ibkr_open_order_observation(
    observation: IBKROpenOrderObservation,
    *,
    registry: IBKROrderIdentityRegistry,
) -> IBKROrderIdentity:
    """Register openOrder identity evidence without producing an economic fact."""

    if not isinstance(observation, IBKROpenOrderObservation):
        raise IBKROrderCallbackError(
            "observation must be an IBKROpenOrderObservation."
        )
    if not isinstance(registry, IBKROrderIdentityRegistry):
        raise IBKROrderCallbackError(
            "registry must be an IBKROrderIdentityRegistry."
        )

    identity = IBKROrderIdentity(
        client_id=observation.client_id,
        session_order_id=observation.session_order_id,
        client_reference=observation.order_reference,
        permanent_order_id=observation.permanent_order_id,
    )
    try:
        return registry.register(identity)
    except IBKRIdentityError as exc:
        raise _protocol_error(
            "IBKR openOrder identity conflicts with previously observed provider identity."
        ) from exc


def map_ibkr_order_status_snapshot(
    observation: IBKROrderStatusObservation,
    *,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> ProviderOrderStateSnapshot:
    """Normalize cumulative orderStatus state without fabricating executions."""

    identity = _ensure_status_identity(
        observation,
        context=context,
        registry=registry,
    )
    if identity.permanent_order_id is None:
        raise _reconciliation_required(
            "IBKR orderStatus has no stable permId yet."
        )

    try:
        provider_identity = identity.to_provider_identity()
    except IBKRIdentityError as exc:
        raise _protocol_error(
            "IBKR orderStatus identity cannot be normalized safely."
        ) from exc

    canonical_status = _snapshot_status(observation)
    return ProviderOrderStateSnapshot(
        order_id=context.order_id,
        identity=provider_identity,
        provider_status=observation.provider_status,
        canonical_status=canonical_status,
        filled_quantity=observation.filled,
        filled_average_price=observation.average_fill_price,
        observed_at=observation.observed_at,
    )


def map_ibkr_order_status_report(
    observation: IBKROrderStatusObservation,
    *,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> ExecutionReport | None:
    """Map only callback states that form complete canonical non-fill facts."""

    snapshot = map_ibkr_order_status_snapshot(
        observation,
        context=context,
        registry=registry,
    )
    rule = ibkr_order_status_rule(observation.provider_status)

    if snapshot.canonical_status is None:
        if rule.disposition is IBKROrderStateDisposition.TRANSIENT:
            return None
        raise _reconciliation_required(
            f"IBKR order status {observation.provider_status!r} requires reconciliation."
        )

    if snapshot.canonical_status in {
        ExecutionStatus.PARTIALLY_FILLED,
        ExecutionStatus.FILLED,
    }:
        raise _reconciliation_required(
            "IBKR cumulative orderStatus fill state requires execDetails before "
            "a canonical economic fill can be emitted."
        )

    return ExecutionReport(
        order_id=context.order_id,
        status=snapshot.canonical_status,
        occurred_at=observation.observed_at,
        correlation_id=context.correlation_id,
        external_order_id=snapshot.identity.external_order_id,
    )


def map_ibkr_order_error_report(
    observation: IBKROrderErrorObservation,
    *,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> ExecutionReport | None:
    """Map only explicit order rejection/cancellation error codes to facts."""

    identity = _ensure_error_identity(
        observation,
        context=context,
        registry=registry,
    )
    external_order_id = (
        str(identity.permanent_order_id)
        if identity.permanent_order_id is not None
        else None
    )

    if observation.error_code == IBKR_ORDER_REJECTED_ERROR_CODE:
        return ExecutionReport(
            order_id=context.order_id,
            status=ExecutionStatus.REJECTED,
            occurred_at=observation.observed_at,
            correlation_id=context.correlation_id,
            external_order_id=external_order_id,
            rejection_reason="IBKR reported order rejection (error 201).",
        )

    if observation.error_code == IBKR_ORDER_CANCELLED_ERROR_CODE:
        return ExecutionReport(
            order_id=context.order_id,
            status=ExecutionStatus.CANCELLED,
            occurred_at=observation.observed_at,
            correlation_id=context.correlation_id,
            external_order_id=external_order_id,
        )

    return None


def _ensure_status_identity(
    observation: IBKROrderStatusObservation,
    *,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> IBKROrderIdentity:
    return _ensure_routing_identity(
        client_id=observation.client_id,
        session_order_id=observation.session_order_id,
        permanent_order_id=observation.permanent_order_id,
        context=context,
        registry=registry,
    )


def _ensure_error_identity(
    observation: IBKROrderErrorObservation,
    *,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> IBKROrderIdentity:
    return _ensure_routing_identity(
        client_id=observation.client_id,
        session_order_id=observation.session_order_id,
        permanent_order_id=None,
        context=context,
        registry=registry,
    )


def _ensure_routing_identity(
    *,
    client_id: IBKRClientId,
    session_order_id: IBKRSessionOrderId,
    permanent_order_id: IBKRPermanentOrderId | None,
    context: ProviderExecutionContext,
    registry: IBKROrderIdentityRegistry,
) -> IBKROrderIdentity:
    if not isinstance(context, ProviderExecutionContext):
        raise IBKROrderCallbackError(
            "context must be a ProviderExecutionContext."
        )
    if not isinstance(registry, IBKROrderIdentityRegistry):
        raise IBKROrderCallbackError(
            "registry must be an IBKROrderIdentityRegistry."
        )

    expected_reference = IBKROrderReference(context.client_order_reference)

    try:
        current = registry.find_by_routing_key(
            client_id=client_id,
            session_order_id=session_order_id,
        )
        if current is not None:
            if current.client_reference != expected_reference:
                raise _protocol_error(
                    "IBKR callback routing identity does not match canonical order reference."
                )
            if permanent_order_id is not None:
                return registry.bind_permanent_order_id(
                    client_id=client_id,
                    session_order_id=session_order_id,
                    permanent_order_id=permanent_order_id,
                )
            return current

        if permanent_order_id is not None:
            durable = registry.find_by_permanent_order_id(permanent_order_id)
            if durable is not None:
                if durable.client_reference != expected_reference:
                    raise _protocol_error(
                        "IBKR permId does not match canonical order reference."
                    )
                return registry.register(
                    IBKROrderIdentity(
                        client_id=client_id,
                        session_order_id=session_order_id,
                        client_reference=durable.client_reference,
                        permanent_order_id=permanent_order_id,
                    )
                )

        return registry.register(
            IBKROrderIdentity(
                client_id=client_id,
                session_order_id=session_order_id,
                client_reference=expected_reference,
                permanent_order_id=permanent_order_id,
            )
        )
    except ProviderProtocolError:
        raise
    except IBKRIdentityError as exc:
        raise _protocol_error(
            "IBKR callback identity conflicts with previously observed provider identity."
        ) from exc


def _snapshot_status(
    observation: IBKROrderStatusObservation,
) -> ExecutionStatus | None:
    provider_status = observation.provider_status
    rule = ibkr_order_status_rule(provider_status)

    if provider_status in {
        IBKROrderStatus.API_CANCELLED.value,
        IBKROrderStatus.CANCELLED.value,
    }:
        return ExecutionStatus.CANCELLED

    if provider_status == IBKROrderStatus.FILLED.value:
        if observation.filled <= 0 or observation.remaining != 0:
            raise _protocol_error(
                "IBKR Filled status requires positive cumulative filled quantity "
                "and zero remaining quantity."
            )
        return ExecutionStatus.FILLED

    if provider_status in {
        IBKROrderStatus.PRE_SUBMITTED.value,
        IBKROrderStatus.SUBMITTED.value,
        IBKROrderStatus.PENDING_CANCEL.value,
    } and observation.filled > 0:
        if observation.remaining == 0:
            return ExecutionStatus.FILLED
        return ExecutionStatus.PARTIALLY_FILLED

    return rule.canonical_status


def _protocol_error(message: str) -> ProviderProtocolError:
    return ProviderProtocolError(
        message,
        provider=IBKR_PROVIDER_KEY,
        operation="order_callback",
    )


def _reconciliation_required(message: str) -> ProviderStateReconciliationRequired:
    return ProviderStateReconciliationRequired(
        message,
        provider=IBKR_PROVIDER_KEY,
        operation="order_callback",
    )
