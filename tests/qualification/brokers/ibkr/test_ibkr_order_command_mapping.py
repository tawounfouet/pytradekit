"""LOT-05.3 qualification for IBKR SDK-free order command mapping."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKROrderAction,
    IBKROrderType,
    IBKRSecurityType,
    IBKRTimeInForce,
    IBKRTransmitPolicy,
    map_ibkr_order_command,
    map_ibkr_stock_contract,
)
from pytradekit.orders.domain import Order, OrderId, OrderSide, TimeInForce
from pytradekit.shared import CorrelationId, InstrumentId, Quantity

_NOW = datetime(2026, 10, 23, 2, 45, tzinfo=UTC)


def test_lot05_3_maps_market_order_without_allocating_provider_order_id() -> None:
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    instrument_id = InstrumentId.new()
    instrument = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=instrument_id,
    )
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("5")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-lot05-3",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    command = map_ibkr_order_command(
        order,
        contract=contract,
        instrument=instrument,
    )

    assert command.order.action is IBKROrderAction.BUY
    assert command.order.order_type is IBKROrderType.MARKET
    assert command.order.time_in_force is IBKRTimeInForce.DAY
    assert command.order.transmit_policy is IBKRTransmitPolicy.TRANSMIT
    assert command.order.order_reference.value == "ptk-lot05-3"
    assert not hasattr(command, "order_id")
    assert not hasattr(command.order, "order_id")
