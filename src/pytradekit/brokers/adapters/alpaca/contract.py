"""Frozen Alpaca integration contract for PyTradeKit 0.5.

This module captures provider-specific decisions proven sufficiently stable by
the Alpaca discovery analysis and PAPER probe harnesses. It deliberately keeps
Alpaca SDK types inside the Alpaca adapter boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.enums import TradeEvent as AlpacaTradeEvent

from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderType, TimeInForce

ALPACA_PROVIDER_KEY: Final = "alpaca"
ALPACA_ENVIRONMENT: Final = "PAPER"
ALPACA_SDK_VERSION_TARGET: Final = "0.44.0"
ALPACA_CLIENT_ORDER_ID_MAX_LENGTH: Final = 128


class AlpacaStateDisposition(StrEnum):
    """How the 0.5 adapter must handle one Alpaca provider state."""

    MAP = "map"
    TRANSIENT = "transient"
    RECONCILE = "reconcile"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True, slots=True)
class AlpacaStateRule:
    """Frozen handling rule for one provider order status or trade event."""

    disposition: AlpacaStateDisposition
    canonical_status: ExecutionStatus | None = None

    def __post_init__(self) -> None:
        if self.disposition is AlpacaStateDisposition.MAP:
            if self.canonical_status is None:
                raise ValueError("Mapped Alpaca state requires a canonical ExecutionStatus.")
            return

        if self.canonical_status is not None:
            raise ValueError(
                "Non-mapped Alpaca state must not declare a canonical ExecutionStatus."
            )


ALPACA_ORDER_STATUS_RULES: Final[Mapping[AlpacaOrderStatus, AlpacaStateRule]] = (
    MappingProxyType(
        {
            AlpacaOrderStatus.ACCEPTED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.ACCEPTED,
            ),
            AlpacaOrderStatus.PENDING_NEW: AlpacaStateRule(
                AlpacaStateDisposition.TRANSIENT
            ),
            AlpacaOrderStatus.NEW: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.ACCEPTED,
            ),
            AlpacaOrderStatus.PARTIALLY_FILLED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.PARTIALLY_FILLED,
            ),
            AlpacaOrderStatus.FILLED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.FILLED,
            ),
            AlpacaOrderStatus.PENDING_CANCEL: AlpacaStateRule(
                AlpacaStateDisposition.TRANSIENT
            ),
            AlpacaOrderStatus.CANCELED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.CANCELLED,
            ),
            AlpacaOrderStatus.EXPIRED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.EXPIRED,
            ),
            AlpacaOrderStatus.REJECTED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.REJECTED,
            ),
            AlpacaOrderStatus.DONE_FOR_DAY: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
            AlpacaOrderStatus.PENDING_REPLACE: AlpacaStateRule(
                AlpacaStateDisposition.OUT_OF_SCOPE
            ),
            AlpacaOrderStatus.REPLACED: AlpacaStateRule(
                AlpacaStateDisposition.OUT_OF_SCOPE
            ),
            AlpacaOrderStatus.PENDING_REVIEW: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
            AlpacaOrderStatus.ACCEPTED_FOR_BIDDING: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
            AlpacaOrderStatus.STOPPED: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
            AlpacaOrderStatus.SUSPENDED: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
            AlpacaOrderStatus.CALCULATED: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
            AlpacaOrderStatus.HELD: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
        }
    )
)


ALPACA_TRADE_EVENT_RULES: Final[Mapping[AlpacaTradeEvent, AlpacaStateRule]] = (
    MappingProxyType(
        {
            AlpacaTradeEvent.ACCEPTED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.ACCEPTED,
            ),
            AlpacaTradeEvent.PENDING_NEW: AlpacaStateRule(
                AlpacaStateDisposition.TRANSIENT
            ),
            AlpacaTradeEvent.NEW: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.ACCEPTED,
            ),
            AlpacaTradeEvent.PARTIAL_FILL: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.PARTIALLY_FILLED,
            ),
            AlpacaTradeEvent.FILL: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.FILLED,
            ),
            AlpacaTradeEvent.PENDING_CANCEL: AlpacaStateRule(
                AlpacaStateDisposition.TRANSIENT
            ),
            AlpacaTradeEvent.CANCELED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.CANCELLED,
            ),
            AlpacaTradeEvent.EXPIRED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.EXPIRED,
            ),
            AlpacaTradeEvent.REJECTED: AlpacaStateRule(
                AlpacaStateDisposition.MAP,
                ExecutionStatus.REJECTED,
            ),
            AlpacaTradeEvent.PENDING_REPLACE: AlpacaStateRule(
                AlpacaStateDisposition.OUT_OF_SCOPE
            ),
            AlpacaTradeEvent.REPLACED: AlpacaStateRule(
                AlpacaStateDisposition.OUT_OF_SCOPE
            ),
            AlpacaTradeEvent.RESTATED: AlpacaStateRule(
                AlpacaStateDisposition.RECONCILE
            ),
        }
    )
)


ALPACA_SUPPORTED_ORDER_TYPES: Final[frozenset[OrderType]] = frozenset(
    {
        OrderType.MARKET,
        OrderType.LIMIT,
    }
)

ALPACA_SUPPORTED_TIME_IN_FORCE: Final[frozenset[TimeInForce]] = frozenset(
    {
        TimeInForce.DAY,
    }
)


def order_status_rule(status: AlpacaOrderStatus) -> AlpacaStateRule:
    """Return the frozen handling rule for an Alpaca order status."""

    return ALPACA_ORDER_STATUS_RULES[status]


def trade_event_rule(event: AlpacaTradeEvent) -> AlpacaStateRule:
    """Return the frozen handling rule for an Alpaca trade event."""

    return ALPACA_TRADE_EVENT_RULES[event]


def validate_client_order_reference(value: str) -> str:
    """Validate one Alpaca client order reference at the adapter boundary."""

    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError("Alpaca client order reference must not be empty.")
    if len(normalized) > ALPACA_CLIENT_ORDER_ID_MAX_LENGTH:
        raise ValueError(
            "Alpaca client order reference exceeds the provider maximum length."
        )
    return normalized


def supports_order_contract(
    *,
    order_type: OrderType,
    time_in_force: TimeInForce,
) -> bool:
    """Return whether the frozen 0.5 Alpaca contract supports this order shape."""

    return (
        order_type in ALPACA_SUPPORTED_ORDER_TYPES
        and time_in_force in ALPACA_SUPPORTED_TIME_IN_FORCE
    )
