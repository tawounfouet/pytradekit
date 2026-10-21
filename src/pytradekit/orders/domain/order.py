"""Order aggregate root and lifecycle invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Self

from pytradekit.orders.domain.errors import (
    InvalidOrderError,
    InvalidOrderTransitionError,
    OrderNotCancellableError,
)
from pytradekit.orders.domain.events import (
    OrderAccepted,
    OrderCancelled,
    OrderCancelRejected,
    OrderCancelRequested,
    OrderCancelUncertain,
    OrderCreated,
    OrderExpired,
    OrderFailed,
    OrderFilled,
    OrderPartiallyFilled,
    OrderRejected,
    OrderSubmitted,
    OrderSubmissionUncertain,
    OrderValidated,
)
from pytradekit.orders.domain.execution_certainty import ExecutionCertainty
from pytradekit.orders.domain.order_id import OrderId
from pytradekit.orders.domain.order_side import OrderSide
from pytradekit.orders.domain.order_status import OrderStatus
from pytradekit.orders.domain.order_type import OrderType
from pytradekit.orders.domain.time_in_force import TimeInForce
from pytradekit.orders.domain.transitions import CANCELLABLE_ORDER_STATUSES, TERMINAL_ORDER_STATUSES
from pytradekit.shared import (
    CorrelationId,
    DomainEvent,
    EventId,
    InstrumentId,
    InvariantViolationError,
    Price,
    Quantity,
    require_utc_datetime,
)


@dataclass(slots=True, kw_only=True)
class Order:
    """Aggregate root controlling canonical order state and invariants."""

    id: OrderId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    time_in_force: TimeInForce
    status: OrderStatus
    filled_quantity: Quantity
    created_at: datetime
    updated_at: datetime
    correlation_id: CorrelationId
    limit_price: Price | None = None
    client_order_id: str | None = None
    external_order_id: str | None = None
    execution_certainty: ExecutionCertainty = ExecutionCertainty.CONFIRMED
    rejection_reason: str | None = None
    failure_reason: str | None = None
    version: int = 0
    cancel_requested: bool = False
    _cancel_previous_status: OrderStatus | None = field(default=None, repr=False)
    _processed_fill_ids: set[str] = field(default_factory=set, repr=False)
    _domain_events: list[DomainEvent] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate aggregate construction invariants."""
        if not isinstance(self.id, OrderId):
            raise InvalidOrderError("Order id must be an OrderId.")
        if not isinstance(self.instrument_id, InstrumentId):
            raise InvalidOrderError("Order instrument_id must be an InstrumentId.")
        if not isinstance(self.side, OrderSide):
            raise InvalidOrderError("Order side must be an OrderSide.")
        if not isinstance(self.order_type, OrderType):
            raise InvalidOrderError("Order order_type must be an OrderType.")
        if not isinstance(self.quantity, Quantity) or self.quantity.value <= 0:
            raise InvalidOrderError("Order quantity must be greater than zero.")
        if not isinstance(self.time_in_force, TimeInForce):
            raise InvalidOrderError("Order time_in_force must be a TimeInForce.")
        if not isinstance(self.status, OrderStatus):
            raise InvalidOrderError("Order status must be an OrderStatus.")
        if not isinstance(self.filled_quantity, Quantity):
            raise InvalidOrderError("Order filled_quantity must be a Quantity.")
        if self.filled_quantity.value > self.quantity.value:
            raise InvalidOrderError("Order filled_quantity cannot exceed order quantity.")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise InvalidOrderError("LIMIT order requires a limit_price.")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise InvalidOrderError("MARKET order must not define a limit_price.")
        if self.client_order_id is not None and not self.client_order_id.strip():
            raise InvalidOrderError("Order client_order_id must not be empty.")
        if self.external_order_id is not None and not self.external_order_id.strip():
            raise InvalidOrderError("Order external_order_id must not be empty.")
        if not isinstance(self.correlation_id, CorrelationId):
            raise InvalidOrderError("Order correlation_id must be a CorrelationId.")
        if type(self.version) is not int or self.version < 0:
            raise InvalidOrderError("Order version must be a non-negative integer.")

        require_utc_datetime(self.created_at, field_name="Order created_at")
        require_utc_datetime(self.updated_at, field_name="Order updated_at")

        if self.status is OrderStatus.FILLED and self.filled_quantity != self.quantity:
            raise InvalidOrderError("FILLED order requires filled_quantity equal to quantity.")

    @classmethod
    def create_market(
        cls,
        *,
        order_id: OrderId,
        instrument_id: InstrumentId,
        side: OrderSide,
        quantity: Quantity,
        time_in_force: TimeInForce,
        correlation_id: CorrelationId,
        occurred_at: datetime,
        client_order_id: str | None = None,
    ) -> Self:
        """Create a canonical market order in CREATED state."""
        return cls._create(
            order_id=order_id,
            instrument_id=instrument_id,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            time_in_force=time_in_force,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            limit_price=None,
            client_order_id=client_order_id,
        )

    @classmethod
    def create_limit(
        cls,
        *,
        order_id: OrderId,
        instrument_id: InstrumentId,
        side: OrderSide,
        quantity: Quantity,
        time_in_force: TimeInForce,
        correlation_id: CorrelationId,
        occurred_at: datetime,
        limit_price: Price,
        client_order_id: str | None = None,
    ) -> Self:
        """Create a canonical limit order in CREATED state."""
        return cls._create(
            order_id=order_id,
            instrument_id=instrument_id,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            time_in_force=time_in_force,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            limit_price=limit_price,
            client_order_id=client_order_id,
        )

    @classmethod
    def _create(
        cls,
        *,
        order_id: OrderId,
        instrument_id: InstrumentId,
        side: OrderSide,
        order_type: OrderType,
        quantity: Quantity,
        time_in_force: TimeInForce,
        correlation_id: CorrelationId,
        occurred_at: datetime,
        limit_price: Price | None,
        client_order_id: str | None,
    ) -> Self:
        timestamp = require_utc_datetime(occurred_at, field_name="Order creation time")
        effective_client_order_id = client_order_id or f"ptk-{order_id}"
        order = cls(
            id=order_id,
            instrument_id=instrument_id,
            side=side,
            order_type=order_type,
            quantity=quantity,
            time_in_force=time_in_force,
            status=OrderStatus.CREATED,
            filled_quantity=Quantity(Decimal("0")),
            limit_price=limit_price,
            client_order_id=effective_client_order_id,
            created_at=timestamp,
            updated_at=timestamp,
            correlation_id=correlation_id,
        )
        order._domain_events.append(
            OrderCreated(
                event_id=EventId.new(),
                occurred_at=timestamp,
                correlation_id=correlation_id,
                order_id=order_id,
            )
        )
        return order

    @property
    def remaining_quantity(self) -> Quantity:
        """Return quantity that has not yet been filled."""
        return Quantity(self.quantity.value - self.filled_quantity.value)

    @property
    def is_terminal(self) -> bool:
        """Return whether the order is in a terminal state."""
        return self.status in TERMINAL_ORDER_STATUSES

    def validate(self, *, occurred_at: datetime) -> None:
        """Move a newly created order to VALIDATED."""
        self._require_status(OrderStatus.CREATED, operation="validate")
        self.status = OrderStatus.VALIDATED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderValidated(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )

    def mark_submitted(self, *, occurred_at: datetime) -> None:
        """Record that a submission attempt has been issued."""
        self._require_status(OrderStatus.VALIDATED, operation="submit")
        self.status = OrderStatus.SUBMITTED
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderSubmitted(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )

    def mark_submission_uncertain(self, *, occurred_at: datetime) -> None:
        """Record uncertainty without treating a timeout as a known failure."""
        self._require_status(OrderStatus.SUBMITTED, operation="mark submission uncertain")
        if self.execution_certainty is ExecutionCertainty.UNCERTAIN:
            return

        self.execution_certainty = ExecutionCertainty.UNCERTAIN
        self._touch(occurred_at)
        self._domain_events.append(
            OrderSubmissionUncertain(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )

    def accept(self, *, external_order_id: str, occurred_at: datetime) -> bool:
        """Apply broker acceptance without allowing state regression."""
        normalized_external_id = self._normalize_external_order_id(external_order_id)

        if self.external_order_id is not None and self.external_order_id != normalized_external_id:
            raise InvariantViolationError("Order external_order_id cannot change silently.")

        if self.status in {
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
            OrderStatus.CANCELLED,
        }:
            return False

        if self.status in {
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_REQUESTED,
            OrderStatus.FILLED,
        }:
            if self.external_order_id is None:
                self.external_order_id = normalized_external_id
                self._touch(occurred_at)
                return True
            return False

        self._require_status(OrderStatus.SUBMITTED, operation="accept")
        self.external_order_id = normalized_external_id
        self.status = OrderStatus.ACCEPTED
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderAccepted(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
                external_order_id=normalized_external_id,
            )
        )
        return True

    def apply_fill(
        self,
        *,
        fill_id: str,
        fill_quantity: Quantity,
        occurred_at: datetime,
        external_order_id: str | None = None,
    ) -> bool:
        """Apply one economic fill exactly once."""
        normalized_fill_id = fill_id.strip() if isinstance(fill_id, str) else ""
        if not normalized_fill_id:
            raise InvalidOrderError("Fill identity must be a non-empty string.")
        if not isinstance(fill_quantity, Quantity) or fill_quantity.value <= 0:
            raise InvalidOrderError("Fill quantity must be greater than zero.")
        if normalized_fill_id in self._processed_fill_ids:
            return False
        if self.status not in {
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_REQUESTED,
        }:
            raise InvalidOrderTransitionError(
                f"Cannot apply fill while order is {self.status.value}."
            )

        if external_order_id is not None:
            normalized_external_id = self._normalize_external_order_id(external_order_id)
            if self.external_order_id is None:
                self.external_order_id = normalized_external_id
            elif self.external_order_id != normalized_external_id:
                raise InvariantViolationError("Order external_order_id cannot change silently.")

        new_filled_value = self.filled_quantity.value + fill_quantity.value
        if new_filled_value > self.quantity.value:
            raise InvariantViolationError("Fill would exceed the order quantity.")

        self._processed_fill_ids.add(normalized_fill_id)
        self.filled_quantity = Quantity(new_filled_value)
        self.execution_certainty = ExecutionCertainty.CONFIRMED

        if self.filled_quantity == self.quantity:
            self.status = OrderStatus.FILLED
            self.cancel_requested = False
            self._cancel_previous_status = None
            self._touch(occurred_at)
            self._domain_events.append(
                OrderFilled(
                    event_id=EventId.new(),
                    occurred_at=self.updated_at,
                    correlation_id=self.correlation_id,
                    order_id=self.id,
                    fill_id=normalized_fill_id,
                    filled_quantity=self.filled_quantity,
                )
            )
            return True

        self.status = OrderStatus.PARTIALLY_FILLED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderPartiallyFilled(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
                fill_id=normalized_fill_id,
                filled_quantity=self.filled_quantity,
            )
        )
        return True

    def request_cancel(self, *, occurred_at: datetime) -> None:
        """Record a cancellation request while awaiting broker confirmation."""
        if self.status not in CANCELLABLE_ORDER_STATUSES:
            raise OrderNotCancellableError(
                f"Order in {self.status.value} state cannot be cancelled."
            )

        self._cancel_previous_status = self.status
        self.cancel_requested = True
        self.status = OrderStatus.CANCEL_REQUESTED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderCancelRequested(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )

    def confirm_cancel(self, *, occurred_at: datetime) -> bool:
        """Apply broker confirmation of cancellation."""
        if self.status is OrderStatus.CANCELLED:
            return False
        if self.status is OrderStatus.FILLED:
            return False
        if self.status is OrderStatus.PARTIALLY_FILLED and self.cancel_requested:
            pass
        elif self.status is not OrderStatus.CANCEL_REQUESTED:
            raise InvalidOrderTransitionError(
                f"Cannot confirm cancellation while order is {self.status.value}."
            )

        self.status = OrderStatus.CANCELLED
        self.cancel_requested = False
        self._cancel_previous_status = None
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderCancelled(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )
        return True

    def reject_cancel(self, *, reason: str, occurred_at: datetime) -> None:
        """Restore the previous active state after a known cancel rejection."""
        normalized_reason = self._normalize_reason(reason, field_name="Cancel rejection reason")
        self._require_status(OrderStatus.CANCEL_REQUESTED, operation="reject cancel")
        restored_status = self._cancel_previous_status
        if restored_status is None:
            raise InvariantViolationError("Cancel rejection requires a previous order status.")

        self.status = restored_status
        self.cancel_requested = False
        self._cancel_previous_status = None
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderCancelRejected(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
                reason=normalized_reason,
                restored_status=restored_status,
            )
        )

    def mark_cancel_uncertain(self, *, occurred_at: datetime) -> None:
        """Record cancellation uncertainty without retrying blindly."""
        self._require_status(OrderStatus.CANCEL_REQUESTED, operation="mark cancel uncertain")
        if self.execution_certainty is ExecutionCertainty.UNCERTAIN:
            return

        self.execution_certainty = ExecutionCertainty.UNCERTAIN
        self._touch(occurred_at)
        self._domain_events.append(
            OrderCancelUncertain(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )

    def reject(self, *, reason: str, occurred_at: datetime) -> bool:
        """Apply a known order rejection and ignore economically stale rejections."""
        normalized_reason = self._normalize_reason(reason, field_name="Order rejection reason")
        if self.status is OrderStatus.REJECTED:
            return False
        if self.status in {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
        }:
            return False
        if self.status not in {OrderStatus.VALIDATED, OrderStatus.SUBMITTED}:
            raise InvalidOrderTransitionError(
                f"Cannot reject order while it is {self.status.value}."
            )

        self.status = OrderStatus.REJECTED
        self.rejection_reason = normalized_reason
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderRejected(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
                reason=normalized_reason,
            )
        )
        return True

    def expire(self, *, occurred_at: datetime) -> bool:
        """Apply a known expiration without regressing a terminal order."""
        if self.status is OrderStatus.EXPIRED:
            return False
        if self.is_terminal:
            return False
        if self.status not in {
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_REQUESTED,
        }:
            raise InvalidOrderTransitionError(
                f"Cannot expire order while it is {self.status.value}."
            )

        self.status = OrderStatus.EXPIRED
        self.cancel_requested = False
        self._cancel_previous_status = None
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderExpired(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
            )
        )
        return True

    def fail(self, *, reason: str, occurred_at: datetime) -> None:
        """Enter FAILED only when failure is known."""
        normalized_reason = self._normalize_reason(reason, field_name="Order failure reason")
        if self.is_terminal:
            raise InvalidOrderTransitionError(
                f"Cannot fail order while it is {self.status.value}."
            )

        self.status = OrderStatus.FAILED
        self.failure_reason = normalized_reason
        self.cancel_requested = False
        self._cancel_previous_status = None
        self.execution_certainty = ExecutionCertainty.CONFIRMED
        self._touch(occurred_at)
        self._domain_events.append(
            OrderFailed(
                event_id=EventId.new(),
                occurred_at=self.updated_at,
                correlation_id=self.correlation_id,
                order_id=self.id,
                reason=normalized_reason,
            )
        )

    def pull_domain_events(self) -> tuple[DomainEvent, ...]:
        """Return and clear domain events recorded since the previous pull."""
        events = tuple(self._domain_events)
        self._domain_events.clear()
        return events

    def has_processed_fill(self, fill_id: str) -> bool:
        """Return whether a fill identity has already been applied."""
        return fill_id in self._processed_fill_ids

    def _touch(self, occurred_at: datetime) -> None:
        timestamp = require_utc_datetime(occurred_at, field_name="Order mutation time")
        if timestamp < self.updated_at:
            raise InvariantViolationError("Order mutation time cannot move backwards.")
        self.updated_at = timestamp
        self.version += 1

    def _require_status(self, required: OrderStatus, *, operation: str) -> None:
        if self.status is not required:
            raise InvalidOrderTransitionError(
                f"Cannot {operation} order from {self.status.value}; expected {required.value}."
            )

    @staticmethod
    def _normalize_reason(reason: str, *, field_name: str) -> str:
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidOrderError(f"{field_name} must be a non-empty string.")
        return reason.strip()

    @staticmethod
    def _normalize_external_order_id(external_order_id: str) -> str:
        if not isinstance(external_order_id, str) or not external_order_id.strip():
            raise InvalidOrderError("External order id must be a non-empty string.")
        return external_order_id.strip()
