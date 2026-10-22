"""Unit tests for the Alpaca PAPER read-only probe harness."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from alpaca.trading.models import TradeUpdate
from alpaca.trading.stream import TradingStream

import pytradekit.brokers.adapters.alpaca.read_only_probe as probe_module
from pytradekit.brokers.adapters.alpaca import (
    AlpacaPaperProbeConfig,
    AlpacaPaperReadOnlyProbe,
    build_alpaca_paper_probe,
)


class _FakeTradingClient:
    def get_account(self) -> object:
        return SimpleNamespace(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            account_number="PA123456789",
            status="ACTIVE",
            currency="USD",
            cash="100000",
            equity="100500",
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
            asset_class="us_equity",
            exchange="NASDAQ",
            symbol=symbol,
            name="Example Asset",
            status="active",
            tradable=True,
            marginable=True,
            shortable=True,
            easy_to_borrow=True,
            fractionable=True,
            min_order_size=0.001,
            min_trade_increment=0.001,
            price_increment=0.01,
        )

    def get_all_positions(self) -> object:
        return []

    def get_orders(self, request: object) -> object:
        del request
        return []


class _FakeDataClient:
    def get_stock_latest_quote(self, request: object) -> object:
        del request
        return {
            "AAPL": SimpleNamespace(
                symbol="AAPL",
                timestamp=datetime(2026, 10, 22, 14, 0, tzinfo=UTC),
                bid_price=100.0,
                bid_size=2.0,
                bid_exchange="V",
                ask_price=100.1,
                ask_size=3.0,
                ask_exchange="V",
            )
        }


class _IdleStream:
    def subscribe_trade_updates(
        self,
        handler: Callable[[TradeUpdate], Coroutine[Any, Any, None]],
    ) -> None:
        del handler

    def run(self) -> None:
        return

    def stop(self) -> None:
        return


class _OneEventStream:
    def __init__(self) -> None:
        self._handler: Callable[[TradeUpdate], Coroutine[Any, Any, None]] | None = None

    def subscribe_trade_updates(
        self,
        handler: Callable[[TradeUpdate], Coroutine[Any, Any, None]],
    ) -> None:
        self._handler = handler

    def run(self) -> None:
        if self._handler is None:
            return
        order = SimpleNamespace(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            client_order_id="PTK-READ-ONLY-OBSERVED",
            symbol="AAPL",
            status="filled",
            filled_qty="1",
        )
        update = cast(
            TradeUpdate,
            SimpleNamespace(
                event="fill",
                execution_id=UUID("44444444-4444-4444-4444-444444444444"),
                timestamp=datetime(2026, 10, 22, 14, 0, tzinfo=UTC),
                order=order,
            ),
        )
        asyncio.run(self._handler(update))

    def stop(self) -> None:
        return


def _config(*, stream_seconds: float = 0.0) -> AlpacaPaperProbeConfig:
    return AlpacaPaperProbeConfig(
        api_key="paper-key",
        secret_key="paper-secret",
        expected_account_id="11111111-1111-1111-1111-111111111111",
        stream_seconds=stream_seconds,
    )


def _probe(
    *,
    stream: _IdleStream | _OneEventStream,
    stream_seconds: float,
) -> AlpacaPaperReadOnlyProbe:
    return AlpacaPaperReadOnlyProbe(
        config=_config(stream_seconds=stream_seconds),
        trading_client=cast(TradingClient, _FakeTradingClient()),
        data_client=cast(StockHistoricalDataClient, _FakeDataClient()),
        trading_stream=cast(TradingStream, stream),
    )


def test_config_repr_does_not_expose_credentials() -> None:
    config = _config()

    rendered = repr(config)

    assert "paper-key" not in rendered
    assert "paper-secret" not in rendered


def test_config_requires_paper_credentials() -> None:
    with pytest.raises(ValueError, match="PYTRADEKIT_ALPACA_PAPER_API_KEY"):
        AlpacaPaperProbeConfig.from_environment({})


def test_config_normalizes_symbol_and_feed() -> None:
    config = AlpacaPaperProbeConfig.from_environment(
        {
            "PYTRADEKIT_ALPACA_PAPER_API_KEY": "key",
            "PYTRADEKIT_ALPACA_PAPER_SECRET_KEY": "secret",
            "PYTRADEKIT_ALPACA_PROBE_SYMBOL": " msft ",
            "PYTRADEKIT_ALPACA_DATA_FEED": "iex",
            "PYTRADEKIT_ALPACA_STREAM_SECONDS": "0",
        }
    )

    assert config.symbol == "MSFT"
    assert config.feed.value == "iex"
    assert config.stream_seconds == 0.0


def test_probe_produces_sanitized_read_only_report() -> None:
    report = _probe(stream=_IdleStream(), stream_seconds=0.0).run()

    assert report.environment == "PAPER"
    assert report.account["id"] == "***1111"
    assert report.account["account_number"] == "***6789"
    assert report.asset["symbol"] == "AAPL"
    assert report.latest_quote["feed"] == "iex"
    assert report.open_orders == []
    assert report.positions == []
    assert report.stream["status"] == "disabled"


def test_probe_rejects_unexpected_account_identity() -> None:
    config = AlpacaPaperProbeConfig(
        api_key="paper-key",
        secret_key="paper-secret",
        expected_account_id="99999999-9999-9999-9999-999999999999",
        stream_seconds=0.0,
    )
    probe = AlpacaPaperReadOnlyProbe(
        config=config,
        trading_client=cast(TradingClient, _FakeTradingClient()),
        data_client=cast(StockHistoricalDataClient, _FakeDataClient()),
        trading_stream=cast(TradingStream, _IdleStream()),
    )

    with pytest.raises(RuntimeError, match="account identity mismatch"):
        probe.run()


def test_trade_update_observation_is_read_only_and_bounded() -> None:
    report = _probe(stream=_OneEventStream(), stream_seconds=0.01).run()

    assert report.stream["status"] == "window_completed"
    assert report.stream["event_count"] == 1
    assert report.trade_updates[0]["event"] == "fill"
    assert report.trade_updates[0]["client_order_id"] == "PTK-READ-ONLY-OBSERVED"


def test_builder_forces_paper_for_trading_and_stream_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_trading_client(**kwargs: object) -> object:
        observed["trading_paper"] = kwargs.get("paper")
        return _FakeTradingClient()

    def fake_data_client(**kwargs: object) -> object:
        observed["data_api_key"] = kwargs.get("api_key")
        return _FakeDataClient()

    def fake_stream(**kwargs: object) -> object:
        observed["stream_paper"] = kwargs.get("paper")
        return _IdleStream()

    monkeypatch.setattr(probe_module, "TradingClient", fake_trading_client)
    monkeypatch.setattr(probe_module, "StockHistoricalDataClient", fake_data_client)
    monkeypatch.setattr(probe_module, "TradingStream", fake_stream)

    probe = build_alpaca_paper_probe(_config())

    assert isinstance(probe, AlpacaPaperReadOnlyProbe)
    assert observed["trading_paper"] is True
    assert observed["stream_paper"] is True
    assert observed["data_api_key"] == "paper-key"