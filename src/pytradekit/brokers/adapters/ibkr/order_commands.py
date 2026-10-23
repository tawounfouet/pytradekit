"""IBKR SDK-free order command mapping for the frozen PAPER execution scope."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pytradekit.orders.domain import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)

from .contract_mapping import (
    IBKRContractRecord,
    IBKRInstrumentMappingResult,
    IBKRPriceIncrementMode,
)
from .identities import IBKROrderReference


class IBKROrderCommandError(ValueError):
    """Raised when a canonical order cannot be represented safely for IBKR."""


class IBKROrderAction(StrEnum):
    """IBKR order action values supported by the frozen scope."""

    BUY = "BUY"
    SELL = "SELL"


class IBKROrderType(StrEnum):
    """IBKR order types supported by the frozen scope."""

    MARKET = "MKT"
    LIMIT = "LMT"


class IBKRTimeInForce(StrEnum):
    """IBKR time-in-force values supported by the frozen scope."""

    DAY = "DAY"


class IBKRTransmitPolicy(StrEnum):
    """Explicit transmission intent for a future TWS placeOrder call."""

    TRANSMIT = "TRANSMIT"


@dataclass(frozen=True, slots=True)
class IBKROrderCommand:
    """SDK-free subset of IBKR Order fields required by LOT-05.3."""

    action: IBKROrderAction
    order_type: IBKROrderType
    total_quantity: Decimal
    time_in_force: IBKRTimeInForce
    order_reference: IBKROrderReference
    limit_price: Decimal | None
    transmit_policy: IBKRTransmitPolicy
    outside_regular_trading_hours: bool
    what_if: bool
    override_percentage_constraints: bool

    def __post_init__(self) -> None:
        if not isinstance(self.action, IBKROrderAction):
            raise IBKROrderCommandError("action must be an IBKROrderAction.")
        if not isinstance(self.order_type, IBKROrderType):
            raise IBKROrderCommandError("order_type must be an IBKROrderType.")
        if (
            not isinstance(self.total_quantity, Decimal)
            or not self.total_quantity.is_finite()
            or self.total_quantity <= 0
        ):
            raise IBKROrderCommandError(
                "total_quantity must be a finite positive Decimal."
            )
        if not isinstance(self.time_in_force, IBKRTimeInForce):
            raise IBKROrderCommandError(
                "time_in_force must be an IBKRTimeInForce."
            )
        if not isinstance(self.order_reference, IBKROrderReference):
            raise IBKROrderCommandError(
                "order_reference must be an IBKROrderReference."
            )
        if not isinstance(self.transmit_policy, IBKRTransmitPolicy):
            raise IBKROrderCommandError(
                "transmit_policy must be an IBKRTransmitPolicy."
            )
        if type(self.outside_regular_trading_hours) is not bool:
            raise IBKROrderCommandError(
                "outside_regular_trading_hours must be a bool."
            )
        if type(self.what_if) is not bool:
            raise IBKROrderCommandError("what_if must be a bool.")
        if type(self.override_percentage_constraints) is not bool:
            raise IBKROrderCommandError(
                "override_percentage_constraints must be a bool."
            )

        if self.order_type is IBKROrderType.MARKET:
            if self.limit_price is not None:
                raise IBKROrderCommandError(
                    "IBKR MARKET command must not define limit_price."
                )
        elif self.limit_price is None:
            raise IBKROrderCommandError(
                "IBKR LIMIT command requires limit_price."
            )

        if self.limit_price is not None and (
            not isinstance(self.limit_price, Decimal)
            or not self.limit_price.is_finite()
            or self.limit_price <= 0
        ):
            raise IBKROrderCommandError(
                "limit_price must be a finite positive Decimal."
            )


@dataclass(frozen=True, slots=True)
class IBKRPlacementCommand:
    """Provider placement envelope without session orderId or SDK objects."""

    contract: IBKRContractRecord
    order: IBKROrderCommand
    price_increment_mode: IBKRPriceIncrementMode

    def __post_init__(self) -> None:
        if not isinstance(self.contract, IBKRContractRecord):
            raise IBKROrderCommandError(
                "contract must be an IBKRContractRecord."
            )
        if not isinstance(self.order, IBKROrderCommand):
            raise IBKROrderCommandError("order must be an IBKROrderCommand.")
        if not isinstance(self.price_increment_mode, IBKRPriceIncrementMode):
            raise IBKROrderCommandError(
                "price_increment_mode must be an IBKRPriceIncrementMode."
            )


def map_ibkr_order_command(
    order: Order,
    *,
    contract: IBKRContractRecord,
    instrument: IBKRInstrumentMappingResult,
) -> IBKRPlacementCommand:
    """Translate one canonical submitted order into an SDK-free IBKR command."""

    if not isinstance(order, Order):
        raise IBKROrderCommandError("order must be a canonical Order.")
    if not isinstance(contract, IBKRContractRecord):
        raise IBKROrderCommandError("contract must be an IBKRContractRecord.")
    if not isinstance(instrument, IBKRInstrumentMappingResult):
        raise IBKROrderCommandError(
            "instrument must be an IBKRInstrumentMappingResult."
        )

    if order.status is not OrderStatus.SUBMITTED:
        raise IBKROrderCommandError(
            "IBKR command mapping requires canonical order status SUBMITTED."
        )
    if order.external_order_id is not None:
        raise IBKROrderCommandError(
            "New IBKR placement cannot start from an order with external_order_id."
        )
    if order.time_in_force is not TimeInForce.DAY:
        raise IBKROrderCommandError(
            "IBKR LOT-05.3 supports DAY orders only."
        )
    if order.instrument_id != instrument.instrument.id:
        raise IBKROrderCommandError(
            "Canonical order instrument does not match the resolved IBKR instrument."
        )

    expected_external_id = str(contract.contract_id)
    if instrument.identity.external_id != expected_external_id:
        raise IBKROrderCommandError(
            "IBKR contract conId does not match resolved provider instrument identity."
        )
    if instrument.identity.external_symbol != contract.symbol:
        raise IBKROrderCommandError(
            "IBKR contract symbol does not match resolved provider instrument identity."
        )
    if instrument.routing_exchange != contract.exchange:
        raise IBKROrderCommandError(
            "IBKR contract routing exchange does not match resolved instrument."
        )
    if instrument.primary_exchange != contract.primary_exchange:
        raise IBKROrderCommandError(
            "IBKR contract primary exchange does not match resolved instrument."
        )

    if not instrument.specification.is_valid_quantity(order.quantity):
        raise IBKROrderCommandError(
            "Canonical order quantity violates the resolved IBKR contract specification."
        )

    client_order_id = order.client_order_id
    if client_order_id is None:
        raise IBKROrderCommandError(
            "Canonical order requires client_order_id for IBKR orderRef."
        )
    order_reference = IBKROrderReference(client_order_id)

    action = (
        IBKROrderAction.BUY
        if order.side is OrderSide.BUY
        else IBKROrderAction.SELL
    )

    if order.order_type is OrderType.MARKET:
        provider_order_type = IBKROrderType.MARKET
        limit_price: Decimal | None = None
    elif order.order_type is OrderType.LIMIT:
        provider_order_type = IBKROrderType.LIMIT
        if order.limit_price is None:
            raise IBKROrderCommandError(
                "Canonical LIMIT order is missing limit_price."
            )
        if order.limit_price.currency != instrument.instrument.quote_currency:
            raise IBKROrderCommandError(
                "Canonical LIMIT price currency does not match the IBKR instrument."
            )
        if (
            instrument.price_increment_mode is IBKRPriceIncrementMode.STATIC
            and not instrument.specification.is_valid_price(order.limit_price)
        ):
            raise IBKROrderCommandError(
                "Canonical LIMIT price violates the static IBKR tick size."
            )
        limit_price = order.limit_price.value
    else:
        raise IBKROrderCommandError(
            f"Unsupported canonical order type {order.order_type.value!r}."
        )

    command = IBKROrderCommand(
        action=action,
        order_type=provider_order_type,
        total_quantity=order.quantity.value,
        time_in_force=IBKRTimeInForce.DAY,
        order_reference=order_reference,
        limit_price=limit_price,
        transmit_policy=IBKRTransmitPolicy.TRANSMIT,
        outside_regular_trading_hours=False,
        what_if=False,
        override_percentage_constraints=False,
    )
    return IBKRPlacementCommand(
        contract=contract,
        order=command,
        price_increment_mode=instrument.price_increment_mode,
    )
