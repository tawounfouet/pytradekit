"""IBKR order session sequencing and callback correlation runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderUnavailableError,
)
from pytradekit.shared import require_utc_datetime

from .discovery import IBKR_PROVIDER_KEY
from .identities import (
    IBKRClientId,
    IBKROrderIdentity,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)
from .identity_registry import IBKROrderIdentityRegistry
from .order_callbacks import (
    IBKROpenOrderObservation,
    IBKROrderErrorObservation,
    IBKROrderStatusObservation,
    register_ibkr_open_order_observation,
)
from .runtime import IBKRPaperConnectionRuntime

IBKR_ORDER_SESSION_VERSION = "0.8.0b5-lot06.4"


class IBKROrderSessionError(ValueError):
    """Raised when provider order-session correlation cannot be established safely."""


class _IBKRRequestIdClient(Protocol):
    def isReady(self) -> bool:
        """Return whether the provider request sequence is ready."""

        ...

    def getReqId(self) -> int:
        """Reserve the next synchronized provider request or order identifier."""

        ...


class _IBKROrderSessionClient(Protocol):
    @property
    def client(self) -> _IBKRRequestIdClient:
        """Expose the synchronized low-level request sequence."""

        ...


class _OrderLike(Protocol):
    orderId: int
    clientId: int
    permId: int
    orderRef: str


class _OrderStatusLike(Protocol):
    orderId: int
    status: str
    filled: object
    remaining: object
    avgFillPrice: object
    permId: int
    clientId: int
    lastFillPrice: object
    whyHeld: str


class _TradeLike(Protocol):
    order: object
    orderStatus: object
    advancedError: str


@dataclass(frozen=True, slots=True)
class IBKROrderSessionReservation:
    """Pre-write correlation facts for one future IBKR economic order."""

    context: ProviderExecutionContext
    client_id: IBKRClientId
    session_order_id: IBKRSessionOrderId
    order_reference: IBKROrderReference

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderExecutionContext):
            raise IBKROrderSessionError(
                "context must be a ProviderExecutionContext."
            )
        if not isinstance(self.client_id, IBKRClientId):
            raise IBKROrderSessionError("client_id must be an IBKRClientId.")
        if not isinstance(self.session_order_id, IBKRSessionOrderId):
            raise IBKROrderSessionError(
                "session_order_id must be an IBKRSessionOrderId."
            )
        if not isinstance(self.order_reference, IBKROrderReference):
            raise IBKROrderSessionError(
                "order_reference must be an IBKROrderReference."
            )
        if self.context.client_order_reference != self.order_reference.value:
            raise IBKROrderSessionError(
                "context client_order_reference must match order_reference."
            )

    @property
    def routing_key(self) -> tuple[int, int]:
        """Return the clientId plus session orderId routing key."""

        return (self.client_id.value, self.session_order_id.value)


@dataclass(frozen=True, slots=True)
class IBKRCorrelatedOpenOrder:
    """Canonical context paired with one openOrder provider observation."""

    reservation: IBKROrderSessionReservation
    observation: IBKROpenOrderObservation


@dataclass(frozen=True, slots=True)
class IBKRCorrelatedOrderStatus:
    """Canonical context paired with one orderStatus provider observation."""

    reservation: IBKROrderSessionReservation
    observation: IBKROrderStatusObservation


@dataclass(frozen=True, slots=True)
class IBKRCorrelatedOrderError:
    """Canonical context paired with one order-scoped provider error."""

    reservation: IBKROrderSessionReservation
    observation: IBKROrderErrorObservation


class IBKROrderCorrelationRegistry:
    """Track canonical execution contexts against provider session routing keys."""

    def __init__(self) -> None:
        self._by_routing_key: dict[
            tuple[int, int],
            IBKROrderSessionReservation,
        ] = {}
        self._by_reference: dict[str, IBKROrderSessionReservation] = {}
        self._by_order_id: dict[str, IBKROrderSessionReservation] = {}

    def register(
        self,
        reservation: IBKROrderSessionReservation,
    ) -> IBKROrderSessionReservation:
        if not isinstance(reservation, IBKROrderSessionReservation):
            raise IBKROrderSessionError(
                "reservation must be an IBKROrderSessionReservation."
            )

        existing_route = self._by_routing_key.get(reservation.routing_key)
        if existing_route is not None and existing_route != reservation:
            raise IBKROrderSessionError(
                "IBKR routing key is already bound to another canonical order."
            )

        reference_key = reservation.order_reference.value
        existing_reference = self._by_reference.get(reference_key)
        if existing_reference is not None and existing_reference != reservation:
            raise IBKROrderSessionError(
                "IBKR orderRef is already bound to another session reservation."
            )

        canonical_key = str(reservation.context.order_id)
        existing_order = self._by_order_id.get(canonical_key)
        if existing_order is not None and existing_order != reservation:
            raise IBKROrderSessionError(
                "Canonical OrderId already has another IBKR session reservation."
            )

        self._by_routing_key[reservation.routing_key] = reservation
        self._by_reference[reference_key] = reservation
        self._by_order_id[canonical_key] = reservation
        return reservation

    def find_by_routing_key(
        self,
        *,
        client_id: IBKRClientId,
        session_order_id: IBKRSessionOrderId,
    ) -> IBKROrderSessionReservation | None:
        if not isinstance(client_id, IBKRClientId):
            raise IBKROrderSessionError("client_id must be an IBKRClientId.")
        if not isinstance(session_order_id, IBKRSessionOrderId):
            raise IBKROrderSessionError(
                "session_order_id must be an IBKRSessionOrderId."
            )
        return self._by_routing_key.get(
            (client_id.value, session_order_id.value)
        )

    def find_by_reference(
        self,
        reference: IBKROrderReference,
    ) -> IBKROrderSessionReservation | None:
        if not isinstance(reference, IBKROrderReference):
            raise IBKROrderSessionError(
                "reference must be an IBKROrderReference."
            )
        return self._by_reference.get(reference.value)

    def __len__(self) -> int:
        return len(self._by_routing_key)


class IBKROrderSessionSequencer:
    """Reserve synchronized IBKR order IDs before any provider economic write."""

    def __init__(
        self,
        *,
        connection: IBKRPaperConnectionRuntime,
        identities: IBKROrderIdentityRegistry,
        correlations: IBKROrderCorrelationRegistry,
    ) -> None:
        if not isinstance(connection, IBKRPaperConnectionRuntime):
            raise IBKROrderSessionError(
                "connection must be an IBKRPaperConnectionRuntime."
            )
        self._connection = connection
        self._identities = identities
        self._correlations = correlations
        self._last_reserved: IBKRSessionOrderId | None = None

    @property
    def last_reserved(self) -> IBKRSessionOrderId | None:
        return self._last_reserved

    def reserve(
        self,
        context: ProviderExecutionContext,
    ) -> IBKROrderSessionReservation:
        if not isinstance(context, ProviderExecutionContext):
            raise IBKROrderSessionError(
                "context must be a ProviderExecutionContext."
            )
        if self._connection.connection_evidence is None:
            raise ProviderUnavailableError(
                "IBKR PAPER runtime must complete startup before order ID reservation.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            )

        client = self._client()
        if not client.isReady():
            raise ProviderProtocolError(
                "IBKR request sequence is not protocol-ready.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            )

        try:
            raw_order_id = client.getReqId()
        except Exception as exc:
            raise ProviderUnavailableError(
                "IBKR synchronized order ID reservation failed "
                f"({type(exc).__name__}).",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            ) from exc

        try:
            session_order_id = IBKRSessionOrderId(raw_order_id)
            order_reference = IBKROrderReference(
                context.client_order_reference
            )
        except ValueError as exc:
            raise ProviderProtocolError(
                "IBKR returned an invalid session order ID sequence.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            ) from exc

        if (
            self._last_reserved is not None
            and session_order_id.value <= self._last_reserved.value
        ):
            raise ProviderProtocolError(
                "IBKR order ID sequence did not advance monotonically.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            )

        client_id = self._connection.profile.client_id
        reservation = IBKROrderSessionReservation(
            context=context,
            client_id=client_id,
            session_order_id=session_order_id,
            order_reference=order_reference,
        )

        try:
            self._identities.register(
                IBKROrderIdentity(
                    client_id=client_id,
                    session_order_id=session_order_id,
                    client_reference=order_reference,
                )
            )
            self._correlations.register(reservation)
        except ValueError as exc:
            raise ProviderProtocolError(
                "IBKR order-session reservation conflicts with existing correlation.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            ) from exc

        self._last_reserved = session_order_id
        return reservation

    def _client(self) -> _IBKRRequestIdClient:
        provider_client = self._connection.read_client()
        if not hasattr(provider_client, "client"):
            raise ProviderUnavailableError(
                "IBKR PAPER client has no synchronized request-ID capability.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            )
        high_level = cast(_IBKROrderSessionClient, provider_client)
        low_level = high_level.client
        if not hasattr(low_level, "getReqId") or not hasattr(low_level, "isReady"):
            raise ProviderUnavailableError(
                "IBKR PAPER low-level client cannot reserve synchronized IDs.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_session_reserve",
            )
        return low_level


class IBKRCallbackCorrelationRouter:
    """Normalize provider callbacks only for explicitly reserved internal orders."""

    def __init__(
        self,
        *,
        expected_client_id: IBKRClientId,
        identities: IBKROrderIdentityRegistry,
        correlations: IBKROrderCorrelationRegistry,
    ) -> None:
        if not isinstance(expected_client_id, IBKRClientId):
            raise IBKROrderSessionError(
                "expected_client_id must be an IBKRClientId."
            )
        self._expected_client_id = expected_client_id
        self._identities = identities
        self._correlations = correlations

    def correlate_open_order(
        self,
        trade: object,
        *,
        observed_at: datetime,
    ) -> IBKRCorrelatedOpenOrder | None:
        order, status = _trade_order_and_status(trade)
        client_id = _client_id(order.clientId)
        session_order_id = _session_order_id(order.orderId)
        reservation = self._reservation(
            client_id=client_id,
            session_order_id=session_order_id,
        )
        if reservation is None:
            return None

        order_reference = _order_reference(order.orderRef)
        if order_reference != reservation.order_reference:
            raise ProviderProtocolError(
                "IBKR openOrder orderRef conflicts with the reserved canonical order.",
                provider=IBKR_PROVIDER_KEY,
                operation="open_order_callback",
            )

        observation = IBKROpenOrderObservation(
            client_id=client_id,
            session_order_id=session_order_id,
            order_reference=order_reference,
            permanent_order_id=_optional_perm_id(order.permId),
            provider_status=_required_text(
                status.status,
                field_name="orderStatus.status",
            ),
            reject_reason=_optional_trade_error(trade),
            observed_at=require_utc_datetime(
                observed_at,
                field_name="IBKR openOrder observed_at",
            ),
        )
        try:
            register_ibkr_open_order_observation(
                observation,
                registry=self._identities,
            )
        except ValueError as exc:
            raise ProviderProtocolError(
                "IBKR openOrder identity conflicts with the reserved session.",
                provider=IBKR_PROVIDER_KEY,
                operation="open_order_callback",
            ) from exc
        return IBKRCorrelatedOpenOrder(
            reservation=reservation,
            observation=observation,
        )

    def correlate_order_status(
        self,
        trade: object,
        *,
        observed_at: datetime,
    ) -> IBKRCorrelatedOrderStatus | None:
        order, status = _trade_order_and_status(trade)
        status_client_id = _client_id(status.clientId)
        order_client_id = _client_id(order.clientId)
        if status_client_id != order_client_id:
            raise ProviderProtocolError(
                "IBKR orderStatus clientId conflicts with Trade.order clientId.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_status_callback",
            )

        status_order_id = _session_order_id(status.orderId)
        order_order_id = _session_order_id(order.orderId)
        if status_order_id != order_order_id:
            raise ProviderProtocolError(
                "IBKR orderStatus orderId conflicts with Trade.order orderId.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_status_callback",
            )

        reservation = self._reservation(
            client_id=status_client_id,
            session_order_id=status_order_id,
        )
        if reservation is None:
            return None

        if _order_reference(order.orderRef) != reservation.order_reference:
            raise ProviderProtocolError(
                "IBKR orderStatus orderRef conflicts with the reserved canonical order.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_status_callback",
            )

        order_perm = _optional_perm_id(order.permId)
        status_perm = _optional_perm_id(status.permId)
        if (
            order_perm is not None
            and status_perm is not None
            and order_perm != status_perm
        ):
            raise ProviderProtocolError(
                "IBKR orderStatus permId conflicts with Trade.order permId.",
                provider=IBKR_PROVIDER_KEY,
                operation="order_status_callback",
            )
        permanent_order_id = status_perm or order_perm

        observation = IBKROrderStatusObservation(
            client_id=status_client_id,
            session_order_id=status_order_id,
            permanent_order_id=permanent_order_id,
            provider_status=_required_text(
                status.status,
                field_name="orderStatus.status",
            ),
            filled=_non_negative_decimal(
                status.filled,
                field_name="orderStatus.filled",
            ),
            remaining=_non_negative_decimal(
                status.remaining,
                field_name="orderStatus.remaining",
            ),
            average_fill_price=_optional_positive_decimal(
                status.avgFillPrice,
                field_name="orderStatus.avgFillPrice",
            ),
            last_fill_price=_optional_positive_decimal(
                status.lastFillPrice,
                field_name="orderStatus.lastFillPrice",
            ),
            why_held=_optional_text(status.whyHeld),
            observed_at=require_utc_datetime(
                observed_at,
                field_name="IBKR orderStatus observed_at",
            ),
        )

        if permanent_order_id is not None:
            try:
                self._identities.bind_permanent_order_id(
                    client_id=status_client_id,
                    session_order_id=status_order_id,
                    permanent_order_id=permanent_order_id,
                )
            except ValueError as exc:
                raise ProviderProtocolError(
                    "IBKR orderStatus permId conflicts with reserved identity.",
                    provider=IBKR_PROVIDER_KEY,
                    operation="order_status_callback",
                ) from exc

        return IBKRCorrelatedOrderStatus(
            reservation=reservation,
            observation=observation,
        )

    def correlate_error(
        self,
        *,
        request_or_order_id: int,
        error_code: int,
        message: str,
        advanced_order_reject_json: str | None,
        observed_at: datetime,
    ) -> IBKRCorrelatedOrderError | None:
        session_order_id = _session_order_id(request_or_order_id)
        reservation = self._correlations.find_by_routing_key(
            client_id=self._expected_client_id,
            session_order_id=session_order_id,
        )
        if reservation is None:
            return None

        observation = IBKROrderErrorObservation(
            client_id=self._expected_client_id,
            session_order_id=session_order_id,
            error_code=error_code,
            message=message,
            advanced_order_reject_json=advanced_order_reject_json,
            observed_at=require_utc_datetime(
                observed_at,
                field_name="IBKR error observed_at",
            ),
        )
        return IBKRCorrelatedOrderError(
            reservation=reservation,
            observation=observation,
        )

    def _reservation(
        self,
        *,
        client_id: IBKRClientId,
        session_order_id: IBKRSessionOrderId,
    ) -> IBKROrderSessionReservation | None:
        if client_id != self._expected_client_id:
            return None
        return self._correlations.find_by_routing_key(
            client_id=client_id,
            session_order_id=session_order_id,
        )


@dataclass(slots=True)
class IBKROrderSessionRuntime:
    """Own sequencing and callback correlation without performing writes."""

    connection: IBKRPaperConnectionRuntime
    identities: IBKROrderIdentityRegistry
    correlations: IBKROrderCorrelationRegistry
    sequencer: IBKROrderSessionSequencer
    callbacks: IBKRCallbackCorrelationRouter

    def reserve(
        self,
        context: ProviderExecutionContext,
    ) -> IBKROrderSessionReservation:
        return self.sequencer.reserve(context)


def build_ibkr_order_session_runtime(
    *,
    connection: IBKRPaperConnectionRuntime,
) -> IBKROrderSessionRuntime:
    """Compose LOT-06.4 over an already started IBKR PAPER connection."""

    if not isinstance(connection, IBKRPaperConnectionRuntime):
        raise IBKROrderSessionError(
            "connection must be an IBKRPaperConnectionRuntime."
        )
    identities = IBKROrderIdentityRegistry()
    correlations = IBKROrderCorrelationRegistry()
    return IBKROrderSessionRuntime(
        connection=connection,
        identities=identities,
        correlations=correlations,
        sequencer=IBKROrderSessionSequencer(
            connection=connection,
            identities=identities,
            correlations=correlations,
        ),
        callbacks=IBKRCallbackCorrelationRouter(
            expected_client_id=connection.profile.client_id,
            identities=identities,
            correlations=correlations,
        ),
    )


def _trade_order_and_status(
    trade: object,
) -> tuple[_OrderLike, _OrderStatusLike]:
    if not hasattr(trade, "order") or not hasattr(trade, "orderStatus"):
        raise IBKROrderSessionError(
            "IBKR Trade callback has an invalid shape."
        )
    candidate = cast(_TradeLike, trade)
    order = candidate.order
    status = candidate.orderStatus
    order_fields = ("orderId", "clientId", "permId", "orderRef")
    status_fields = (
        "orderId",
        "status",
        "filled",
        "remaining",
        "avgFillPrice",
        "permId",
        "clientId",
        "lastFillPrice",
        "whyHeld",
    )
    if any(not hasattr(order, field) for field in order_fields):
        raise IBKROrderSessionError(
            "IBKR Trade.order callback has an invalid shape."
        )
    if any(not hasattr(status, field) for field in status_fields):
        raise IBKROrderSessionError(
            "IBKR Trade.orderStatus callback has an invalid shape."
        )
    return cast(_OrderLike, order), cast(_OrderStatusLike, status)


def _client_id(value: object) -> IBKRClientId:
    if type(value) is not int:
        raise IBKROrderSessionError("IBKR clientId must be an integer.")
    return IBKRClientId(value)


def _session_order_id(value: object) -> IBKRSessionOrderId:
    if type(value) is not int:
        raise IBKROrderSessionError("IBKR orderId must be an integer.")
    return IBKRSessionOrderId(value)


def _optional_perm_id(value: object) -> IBKRPermanentOrderId | None:
    if type(value) is not int:
        raise IBKROrderSessionError("IBKR permId must be an integer.")
    if value == 0:
        return None
    return IBKRPermanentOrderId(value)


def _order_reference(value: object) -> IBKROrderReference:
    if not isinstance(value, str):
        raise IBKROrderSessionError("IBKR orderRef must be a string.")
    return IBKROrderReference(value)


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKROrderSessionError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKROrderSessionError(f"{field_name} must be non-empty.")
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise IBKROrderSessionError(
            "optional provider text must be a string or None."
        )
    normalized = value.strip()
    return normalized or None


def _non_negative_decimal(
    value: object,
    *,
    field_name: str,
) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise IBKROrderSessionError(
            f"{field_name} is not numeric."
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise IBKROrderSessionError(
            f"{field_name} must be a finite non-negative value."
        )
    return parsed


def _optional_positive_decimal(
    value: object,
    *,
    field_name: str,
) -> Decimal | None:
    parsed = _non_negative_decimal(value, field_name=field_name)
    return parsed if parsed > 0 else None


def _optional_trade_error(trade: object) -> str | None:
    if not hasattr(trade, "advancedError"):
        return None
    return _optional_text(getattr(trade, "advancedError"))
