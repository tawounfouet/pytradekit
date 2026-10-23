"""Unit tests for IBKR SDK-free order command mapping."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKROrderAction,
    IBKROrderCommandError,
    IBKROrderType,
    IBKRPriceIncrementMode,
    IBKRSecurityType,
    IBKRTimeInForce,
    IBKRTransmitPolicy,
    map_ibkr_order_command,
    map_ibkr_stock_contract,
)
from pytradekit.orders.domain import Order, OrderId, OrderSide, TimeInForce
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Price, Quantity

_NOW = datetime(2026, 10, 23, 2, 30, tzinfo=UTC)


def _instrument(*, market_rule: bool = False):
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
        trading_class="NMS",
    )
    details = IBKRContractDetailsRecord(
        contract=contract,
        min_tick=Decimal("0.01"),
        min_size=Decimal("1"),
        size_increment=Decimal("1"),
        valid_exchanges=("SMART",),
        market_rule_ids=((26,) if market_rule else ()),
    )
    instrument_id = InstrumentId.new()
    mapping = map_ibkr_stock_contract(details, instrument_id=instrument_id)
    return contract, mapping, instrument_id


def _market_order(*, side: OrderSide = OrderSide.BUY, tif: TimeInForce = TimeInForce.DAY):
    _contract, _mapping, instrument_id = _instrument()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=side,
        quantity=Quantity(Decimal("10")),
        time_in_force=tif,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-market-1",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)
    return order


def test_market_buy_maps_to_explicit_transmitted_day_command() -> None:
    contract, mapping, instrument_id = _instrument()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("10")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-market-1",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    placement = map_ibkr_order_command(
        order,
        contract=contract,
        instrument=mapping,
    )

    assert placement.order.action is IBKROrderAction.BUY
    assert placement.order.order_type is IBKROrderType.MARKET
    assert placement.order.total_quantity == Decimal("10")
    assert placement.order.time_in_force is IBKRTimeInForce.DAY
    assert placement.order.order_reference.value == "ptk-market-1"
    assert placement.order.limit_price is None
    assert placement.order.transmit_policy is IBKRTransmitPolicy.TRANSMIT
    assert not placement.order.outside_regular_trading_hours
    assert not placement.order.what_if
    assert not placement.order.override_percentage_constraints


def test_sell_limit_maps_price_without_float_conversion() -> None:
    contract, mapping, instrument_id = _instrument()
    price = Price(Decimal("250.12"), Currency("USD"))
    order = Order.create_limit(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("3")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        limit_price=price,
        client_order_id="ptk-limit-1",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    placement = map_ibkr_order_command(
        order,
        contract=contract,
        instrument=mapping,
    )

    assert placement.order.action is IBKROrderAction.SELL
    assert placement.order.order_type is IBKROrderType.LIMIT
    assert placement.order.limit_price == Decimal("250.12")
    assert isinstance(placement.order.limit_price, Decimal)


def test_static_tick_validation_rejects_invalid_limit_price() -> None:
    contract, mapping, instrument_id = _instrument()
    order = Order.create_limit(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        limit_price=Price(Decimal("250.123"), Currency("USD")),
        client_order_id="ptk-limit-bad-tick",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    with pytest.raises(IBKROrderCommandError, match="tick size"):
        map_ibkr_order_command(order, contract=contract, instrument=mapping)


def test_market_rule_price_is_not_rejected_by_fake_static_tick() -> None:
    contract, mapping, instrument_id = _instrument(market_rule=True)
    order = Order.create_limit(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        limit_price=Price(Decimal("250.123"), Currency("USD")),
        client_order_id="ptk-limit-market-rule",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    placement = map_ibkr_order_command(order, contract=contract, instrument=mapping)

    assert placement.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE
    assert placement.order.limit_price == Decimal("250.123")


def test_quantity_constraints_are_checked_before_transport() -> None:
    contract, mapping, instrument_id = _instrument()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1.5")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-fractional",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    with pytest.raises(IBKROrderCommandError, match="quantity"):
        map_ibkr_order_command(order, contract=contract, instrument=mapping)


def test_gtc_is_rejected_by_frozen_day_only_scope() -> None:
    contract, mapping, instrument_id = _instrument()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.GTC,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-gtc",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    with pytest.raises(IBKROrderCommandError, match="DAY"):
        map_ibkr_order_command(order, contract=contract, instrument=mapping)


def test_mapping_requires_submitted_order() -> None:
    contract, mapping, instrument_id = _instrument()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-created",
    )

    with pytest.raises(IBKROrderCommandError, match="SUBMITTED"):
        map_ibkr_order_command(order, contract=contract, instrument=mapping)


def test_mapping_rejects_existing_external_order_identity() -> None:
    contract, mapping, instrument_id = _instrument()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-existing",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)
    order.external_order_id = "700"

    with pytest.raises(IBKROrderCommandError, match="external_order_id"):
        map_ibkr_order_command(order, contract=contract, instrument=mapping)


def test_mapping_rejects_contract_identity_mismatch() -> None:
    _contract, mapping, instrument_id = _instrument()
    wrong_contract = IBKRContractRecord(
        contract_id=IBKRContractId(999999),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=_NOW,
        client_order_id="ptk-mismatch",
    )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)

    with pytest.raises(IBKROrderCommandError, match="conId"):
        map_ibkr_order_command(order, contract=wrong_contract, instrument=mapping)
