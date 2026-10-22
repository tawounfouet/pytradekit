"""Unit tests for the controlled Alpaca PAPER order probe."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from alpaca.trading.models import Order
from alpaca.trading.requests import OrderRequest
from alpaca.trading.stream import TradingStream

from pytradekit.brokers.adapters.alpaca.controlled_order_probe import (
    AlpacaPaperControlledOrderProbe,
    AlpacaPaperOrderProbeConfig,
    AlpacaSimulatedResponseLoss,
    AlpacaSingleAttemptTradingClient,
)


def _config() -> AlpacaPaperOrderProbeConfig:
    return AlpacaPaperOrderProbeConfig(
        api_key="paper-key",
        secret_key="paper-secret",
        expected_account_id="11111111-1111-1111-1111-111111111111",
        acknowledgement="I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED",
        market_qty=Decimal("0.001"),
        limit_qty=Decimal("1"),
        order_timeout_seconds=0.2,
        poll_interval_seconds=0.001,
        stream_warmup_seconds=0.0,
        stream_tail_seconds=0.0,
    )


def _order(
    *,
    client_order_id: str,
    side: OrderSide,
    order_type: OrderType,
    status: OrderStatus,
    qty: str,
    filled_qty: str,
    limit_price: str | None = None,
) -> object:
    return SimpleNamespace(
        id=uuid4(),
        client_order_id=client_order_id,
        symbol="AAPL",
        status=status,
        type=order_type,
        side=side,
        time_in_force=TimeInForce.DAY,
        qty=qty,
        filled_qty=filled_qty,
        filled_avg_price="100.00" if filled_qty != "0" else None,
        limit_price=limit_price,
        submitted_at=datetime(2026, 10, 22, 14, 0, tzinfo=UTC),
    )


class _State:
    def __init__(self) -> None:
        self.position = Decimal("0")
        self.orders: dict[str, object] = {}
        self.submit_attempts: dict[str, int] = {}
        self.cancel_attempts = 0


class _FakeReadClient:
    def __init__(self, state: _State) -> None:
        self._state = state

    def get_account(self) -> object:
        return SimpleNamespace(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            account_number="PA123456789",
            status="ACTIVE",
            currency="USD",
            cash="100000",
            equity="100000",
            buying_power="200000",
            trading_blocked=False,
            account_blocked=False,
        )

    def get_clock(self) -> object:
        now = datetime(2026, 10, 22, 14, 0, tzinfo=UTC)
        return SimpleNamespace(
            timestamp=now,
            is_open=True,
            next_open=now + timedelta(days=1),
            next_close=now + timedelta(hours=2),
        )

    def get_asset(self, symbol: str) -> object:
        return SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            symbol=symbol,
            tradable=True,
            fractionable=True,
            min_order_size=0.001,
            min_trade_increment=0.001,
            price_increment=0.01,
        )

    def get_order_by_client_id(self, client_order_id: str) -> object:
        return self._state.orders[client_order_id]

    def get_all_positions(self) -> object:
        if self._state.position == 0:
            return []
        side = "long" if self._state.position > 0 else "short"
        return [
            SimpleNamespace(
                symbol="AAPL",
                qty=str(abs(self._state.position)),
                side=side,
            )
        ]


class _FakeCommandClient:
    def __init__(self, state: _State) -> None:
        self._state = state

    @property
    def sdk_retry_attempts(self) -> int:
        return 0

    @property
    def cancel_attempts(self) -> int:
        return self._state.cancel_attempts

    def submit_attempts_for(self, client_order_id: str) -> int:
        return self._state.submit_attempts.get(client_order_id, 0)

    def submit_once(
        self,
        request: OrderRequest,
        *,
        simulate_response_loss: bool = False,
    ) -> object:
        client_order_id = cast(str, request.client_order_id)
        self._state.submit_attempts[client_order_id] = (
            self._state.submit_attempts.get(client_order_id, 0) + 1
        )
        side = cast(OrderSide, request.side)
        qty = Decimal(str(request.qty))
        order_type = cast(OrderType, request.type)

        if order_type is OrderType.MARKET:
            status = OrderStatus.FILLED
            filled_qty = str(qty)
            self._state.position += qty if side is OrderSide.BUY else -qty
            limit_price = None
        else:
            status = OrderStatus.NEW
            filled_qty = "0"
            limit_price = str(request.limit_price)

        order = _order(
            client_order_id=client_order_id,
            side=side,
            order_type=order_type,
            status=status,
            qty=str(qty),
            filled_qty=filled_qty,
            limit_price=limit_price,
        )
        self._state.orders[client_order_id] = order

        if simulate_response_loss:
            raise AlpacaSimulatedResponseLoss("simulated")
        return order

    def cancel_once(self, order_id: str) -> None:
        self._state.cancel_attempts += 1
        for client_order_id, current in list(self._state.orders.items()):
            current_order = cast(SimpleNamespace, current)
            if str(current_order.id) != order_id:
                continue
            self._state.orders[client_order_id] = _order(
                client_order_id=client_order_id,
                side=cast(OrderSide, current_order.side),
                order_type=cast(OrderType, current_order.type),
                status=OrderStatus.CANCELED,
                qty=str(current_order.qty),
                filled_qty=str(current_order.filled_qty),
                limit_price=cast(str | None, current_order.limit_price),
            )
            return


class _FakeDataClient:
    def get_stock_latest_quote(self, request: StockLatestQuoteRequest) -> object:
        symbol = cast(str, request.symbol_or_symbols)
        return {
            symbol: SimpleNamespace(
                symbol=symbol,
                timestamp=datetime(2026, 10, 22, 14, 0, tzinfo=UTC),
                bid_price=100.0,
                bid_size=10.0,
                bid_exchange="V",
                ask_price=100.1,
                ask_size=10.0,
                ask_exchange="V",
            )
        }


class _IdleStream:
    def subscribe_trade_updates(self, handler: object) -> None:
        del handler

    def run(self) -> None:
        return

    def stop(self) -> None:
        return


def test_config_requires_explicit_write_acknowledgement() -> None:
    with pytest.raises(ValueError, match="PYTRADEKIT_ALPACA_ORDER_PROBE_ACK"):
        AlpacaPaperOrderProbeConfig(
            api_key="key",
            secret_key="secret",
            expected_account_id="paper-account",
            acknowledgement="",
        )


def test_config_requires_expected_account_for_write_probe() -> None:
    with pytest.raises(ValueError, match="EXPECTED_ACCOUNT_ID"):
        AlpacaPaperOrderProbeConfig(
            api_key="key",
            secret_key="secret",
            expected_account_id="",
            acknowledgement="I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED",
        )


def test_config_repr_redacts_credentials_and_acknowledgement() -> None:
    rendered = repr(_config())

    assert "paper-key" not in rendered
    assert "paper-secret" not in rendered
    assert "I_UNDERSTAND" not in rendered


def test_single_attempt_client_disables_sdk_retries_and_never_resubmits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AlpacaSingleAttemptTradingClient(api_key="paper-key", secret_key="paper-secret")
    calls = 0
    response = cast(
        Order,
        _order(
            client_order_id="PTK45-MKT-test",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            qty="0.001",
            filled_qty="0.001",
        ),
    )

    def fake_submit(order_data: object) -> object:
        nonlocal calls
        del order_data
        calls += 1
        return response

    monkeypatch.setattr(client, "submit_order", fake_submit)

    request = SimpleNamespace(client_order_id="PTK45-MKT-test")
    with pytest.raises(AlpacaSimulatedResponseLoss):
        client.submit_once(
            cast(Any, request),
            simulate_response_loss=True,
        )

    assert client.sdk_retry_attempts == 0
    assert client.submit_attempts_for("PTK45-MKT-test") == 1
    assert calls == 1


def test_controlled_probe_recovers_market_by_client_id_and_restores_position() -> None:
    state = _State()
    command = _FakeCommandClient(state)
    probe = AlpacaPaperControlledOrderProbe(
        config=_config(),
        read_client=cast(TradingClient, _FakeReadClient(state)),
        command_client=cast(AlpacaSingleAttemptTradingClient, command),
        data_client=cast(StockHistoricalDataClient, _FakeDataClient()),
        trading_stream=cast(TradingStream, _IdleStream()),
    )

    report = probe.run()

    assert report.result == "PASS"
    assert report.uncertain_recovery["certainty_before_recovery"] == "UNCERTAIN"
    assert report.uncertain_recovery["simulated_post_ack_response_loss"] is True
    assert report.uncertain_recovery["resubmitted"] is False
    assert report.transport_safety["sdk_retry_attempts"] == 0
    assert report.transport_safety["market_submit_attempts"] == 1
    assert report.transport_safety["limit_submit_attempts"] == 1
    assert report.transport_safety["cleanup_submit_attempts"] == 1
    assert report.transport_safety["cancel_attempts"] == 1
    assert report.limit_order["status"] == "canceled"
    assert Decimal(cast(str, report.limit_order["configured_limit_price"])) < Decimal("100")
    assert report.baseline_position_qty == "0"
    assert report.final_position_qty == "0"
    assert state.position == 0