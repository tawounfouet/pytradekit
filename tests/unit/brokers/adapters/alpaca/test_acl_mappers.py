"""Unit tests for Alpaca anti-corruption mapping semantics."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from alpaca.trading.models import Asset, Order, Position, TradeAccount, TradeUpdate

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.alpaca.mappers import (
    map_account_snapshot,
    map_asset_snapshot,
    map_order_query_report,
    map_order_state_snapshot,
    map_position_snapshot,
    map_submission_ack,
    map_trade_update_report,
)
from pytradekit.execution import ExecutionStatus, SubmissionStatus
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import CorrelationId, Currency, InstrumentId

NOW = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)


def _context(client_order_id: str = "ptk-order-1") -> ProviderExecutionContext:
    return ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference=client_order_id,
        quote_currency=Currency("USD"),
    )


def _order(
    *,
    status: str = "new",
    client_order_id: str = "ptk-order-1",
    filled_qty: str = "0",
    filled_avg_price: str | None = None,
) -> Order:
    return Order.model_validate(
        {
            "id": str(uuid4()),
            "client_order_id": client_order_id,
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
            "submitted_at": NOW.isoformat(),
            "symbol": "AAPL",
            "asset_class": "us_equity",
            "qty": "1",
            "filled_qty": filled_qty,
            "filled_avg_price": filled_avg_price,
            "order_class": "simple",
            "type": "market",
            "side": "buy",
            "time_in_force": "day",
            "status": status,
            "extended_hours": False,
        }
    )


def test_asset_mapper_preserves_canonical_identity_and_decimal_constraints() -> None:
    instrument_id = InstrumentId.new()
    asset = Asset.model_validate(
        {
            "id": str(uuid4()),
            "class": "us_equity",
            "exchange": "NASDAQ",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "status": "active",
            "tradable": True,
            "marginable": True,
            "shortable": True,
            "easy_to_borrow": True,
            "fractionable": True,
            "min_order_size": 0.001,
            "min_trade_increment": 0.001,
            "price_increment": 0.01,
        }
    )

    snapshot = map_asset_snapshot(asset, instrument_id=instrument_id, observed_at=NOW)

    assert snapshot.instrument.id == instrument_id
    assert snapshot.mapping.external_id == str(asset.id)
    assert snapshot.mapping.external_symbol == "AAPL"
    assert snapshot.specification.tick_size == Decimal("0.01")
    assert snapshot.specification.quantity_step == Decimal("0.001")
    assert snapshot.specification.min_quantity == Decimal("0.001")
    assert snapshot.tradable is True


def test_account_mapper_keeps_cash_and_buying_power_semantically_separate() -> None:
    account_id = AccountId.new()
    account = TradeAccount.model_validate(
        {
            "id": str(uuid4()),
            "account_number": "PA123456",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": "1000.25",
            "buying_power": "2000.50",
            "equity": "1500.75",
            "portfolio_value": "1500.75",
            "trading_blocked": False,
            "account_blocked": False,
        }
    )

    snapshot = map_account_snapshot(account, account_id=account_id, observed_at=NOW)

    assert snapshot.account.id == account_id
    assert snapshot.cash_balance is not None
    assert snapshot.cash_balance.cash.amount == Decimal("1000.25")
    assert snapshot.cash_balance.available is None
    assert snapshot.buying_power is not None
    assert snapshot.buying_power.amount == Decimal("2000.50")
    assert snapshot.identity.external_account_id == str(account.id)


def test_position_mapper_uses_signed_quantity_and_does_not_fabricate_realized_pnl() -> None:
    position = Position.model_validate(
        {
            "asset_id": str(uuid4()),
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "asset_class": "us_equity",
            "avg_entry_price": "190.125",
            "qty": "2.5",
            "side": "short",
            "market_value": "-475.00",
            "cost_basis": "475.3125",
            "unrealized_pl": "0.3125",
            "current_price": "190.00",
            "qty_available": "2.0",
        }
    )

    snapshot = map_position_snapshot(
        position,
        account_id=AccountId.new(),
        instrument_id=InstrumentId.new(),
        quote_currency=Currency("USD"),
        observed_at=NOW,
    )

    assert snapshot.signed_quantity == Decimal("-2.5")
    assert snapshot.average_price.value == Decimal("190.125")
    assert snapshot.current_price is not None
    assert snapshot.current_price.value == Decimal("190.00")
    assert snapshot.available_quantity == Decimal("2.0")


def test_trade_update_fill_maps_to_canonical_fill_with_external_execution_id() -> None:
    context = _context()
    execution_id = uuid4()
    update = TradeUpdate.model_validate(
        {
            "event": "fill",
            "execution_id": str(execution_id),
            "order": _order(status="filled", filled_qty="1", filled_avg_price="191.25"),
            "timestamp": NOW.isoformat(),
            "price": 191.25,
            "qty": 1.0,
        }
    )

    report = map_trade_update_report(update, context=context)

    assert report is not None
    assert report.status is ExecutionStatus.FILLED
    assert report.fill is not None
    assert report.fill.external_fill_id == str(execution_id)
    assert report.fill.quantity.value == Decimal("1.0")
    assert report.fill.price.value == Decimal("191.25")
    assert str(report.fill.id) != str(execution_id)


def test_trade_update_pending_event_does_not_create_domain_state() -> None:
    context = _context()
    update = TradeUpdate.model_validate(
        {
            "event": "pending_new",
            "order": _order(status="pending_new"),
            "timestamp": NOW.isoformat(),
        }
    )

    assert map_trade_update_report(update, context=context) is None


def test_order_query_filled_requires_fill_reconciliation_instead_of_fabrication() -> None:
    context = _context()
    order = _order(status="filled", filled_qty="1", filled_avg_price="191.25")

    with pytest.raises(ProviderStateReconciliationRequired, match="individual executions"):
        map_order_query_report(order, context=context)


def test_order_query_cancelled_maps_without_fill() -> None:
    context = _context()
    order = _order(status="canceled")

    report = map_order_query_report(order, context=context)

    assert report is not None
    assert report.status is ExecutionStatus.CANCELLED
    assert report.fill is None


def test_order_state_snapshot_preserves_provider_and_canonical_status() -> None:
    context = _context()
    order = _order(status="partially_filled", filled_qty="0.5", filled_avg_price="190.50")

    snapshot = map_order_state_snapshot(order, context=context)

    assert snapshot.order_id == context.order_id
    assert snapshot.canonical_status is ExecutionStatus.PARTIALLY_FILLED
    assert snapshot.provider_status == "partially_filled"
    assert snapshot.filled_quantity == Decimal("0.5")
    assert snapshot.filled_average_price == Decimal("190.50")


def test_submission_ack_requires_matching_client_reference() -> None:
    result = map_submission_ack(
        _order(status="accepted"),
        expected_client_order_reference="ptk-order-1",
    )

    assert result.status is SubmissionStatus.ACKNOWLEDGED
    assert result.external_order_id is not None

    with pytest.raises(ProviderProtocolError, match="client_order_id"):
        map_submission_ack(
            _order(status="accepted", client_order_id="different"),
            expected_client_order_reference="ptk-order-1",
        )
