"""Read-only Alpaca PAPER discovery probe.

This module deliberately exposes no order submission, cancellation, replacement,
position-closing, or option-exercise operation. It exists to qualify connectivity
and provider facts before the production Alpaca adapter is implemented.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import Thread
from time import monotonic, sleep
from typing import cast

from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.models.quotes import Quote
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Asset, Clock, Order, Position, TradeAccount, TradeUpdate
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.stream import TradingStream

type ProbeScalar = str | bool | int | float | None
type ProbeRow = dict[str, ProbeScalar]

_API_KEY_ENV = "PYTRADEKIT_ALPACA_PAPER_API_KEY"
_SECRET_KEY_ENV = "PYTRADEKIT_ALPACA_PAPER_SECRET_KEY"
_EXPECTED_ACCOUNT_ENV = "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID"
_SYMBOL_ENV = "PYTRADEKIT_ALPACA_PROBE_SYMBOL"
_FEED_ENV = "PYTRADEKIT_ALPACA_DATA_FEED"
_STREAM_SECONDS_ENV = "PYTRADEKIT_ALPACA_STREAM_SECONDS"


@dataclass(frozen=True, slots=True)
class AlpacaPaperProbeConfig:
    """Configuration for a PAPER-only, read-only Alpaca probe."""

    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    expected_account_id: str | None = None
    symbol: str = "AAPL"
    feed: DataFeed = DataFeed.IEX
    stream_seconds: float = 5.0

    def __post_init__(self) -> None:
        api_key = self.api_key.strip()
        secret_key = self.secret_key.strip()
        symbol = self.symbol.strip().upper()
        expected_account_id = (
            self.expected_account_id.strip() if self.expected_account_id is not None else None
        )

        if not api_key:
            raise ValueError(f"{_API_KEY_ENV} must be set")
        if not secret_key:
            raise ValueError(f"{_SECRET_KEY_ENV} must be set")
        if not symbol:
            raise ValueError("Probe symbol must not be empty")
        if self.stream_seconds < 0:
            raise ValueError("Stream observation duration must be greater than or equal to zero")

        object.__setattr__(self, "api_key", api_key)
        object.__setattr__(self, "secret_key", secret_key)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "expected_account_id", expected_account_id or None)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> AlpacaPaperProbeConfig:
        """Build configuration from environment variables only.

        No LIVE environment selector exists by design.
        """

        source = os.environ if environ is None else environ
        api_key = source.get(_API_KEY_ENV, "")
        secret_key = source.get(_SECRET_KEY_ENV, "")
        expected_account_id = source.get(_EXPECTED_ACCOUNT_ENV) or None
        symbol = source.get(_SYMBOL_ENV, "AAPL")
        feed_text = source.get(_FEED_ENV, DataFeed.IEX.value).strip().lower()
        stream_seconds_text = source.get(_STREAM_SECONDS_ENV, "5")

        try:
            feed = DataFeed(feed_text)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in DataFeed)
            raise ValueError(
                f"{_FEED_ENV} must be one of: {allowed}"
            ) from exc

        try:
            stream_seconds = float(stream_seconds_text)
        except ValueError as exc:
            raise ValueError(f"{_STREAM_SECONDS_ENV} must be a number") from exc

        return cls(
            api_key=api_key,
            secret_key=secret_key,
            expected_account_id=expected_account_id,
            symbol=symbol,
            feed=feed,
            stream_seconds=stream_seconds,
        )


@dataclass(frozen=True, slots=True)
class AlpacaPaperProbeReport:
    """Sanitized observation report produced by the read-only probe."""

    generated_at: str
    environment: str
    sdk_version_target: str
    account: ProbeRow
    clock: ProbeRow
    asset: ProbeRow
    positions: list[ProbeRow]
    open_orders: list[ProbeRow]
    latest_quote: ProbeRow
    trade_updates: list[ProbeRow]
    stream: ProbeRow
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return {
            "generated_at": self.generated_at,
            "environment": self.environment,
            "sdk_version_target": self.sdk_version_target,
            "account": self.account,
            "clock": self.clock,
            "asset": self.asset,
            "positions": self.positions,
            "open_orders": self.open_orders,
            "latest_quote": self.latest_quote,
            "trade_updates": self.trade_updates,
            "stream": self.stream,
            "warnings": self.warnings,
        }


class AlpacaPaperReadOnlyProbe:
    """Execute read-only Alpaca PAPER observations."""

    def __init__(
        self,
        *,
        config: AlpacaPaperProbeConfig,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        trading_stream: TradingStream,
    ) -> None:
        self._config = config
        self._trading_client = trading_client
        self._data_client = data_client
        self._trading_stream = trading_stream

    def run(self) -> AlpacaPaperProbeReport:
        """Run all read-only checks and return a sanitized report."""

        account = cast(TradeAccount, self._trading_client.get_account())
        self._verify_expected_account(account)

        clock = cast(Clock, self._trading_client.get_clock())
        asset = cast(Asset, self._trading_client.get_asset(self._config.symbol))
        positions = cast(list[Position], self._trading_client.get_all_positions())
        open_orders = cast(
            list[Order],
            self._trading_client.get_orders(
                GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=100)
            ),
        )
        quote = self._latest_quote()
        trade_updates, stream_summary, warnings = self._observe_trade_updates()

        return AlpacaPaperProbeReport(
            generated_at=datetime.now(UTC).isoformat(),
            environment="PAPER",
            sdk_version_target="alpaca-py==0.44.0",
            account=_account_row(account),
            clock=_clock_row(clock),
            asset=_asset_row(asset),
            positions=[_position_row(position) for position in positions],
            open_orders=[_order_row(order) for order in open_orders],
            latest_quote=_quote_row(quote, feed=self._config.feed),
            trade_updates=trade_updates,
            stream=stream_summary,
            warnings=warnings,
        )

    def _verify_expected_account(self, account: TradeAccount) -> None:
        expected = self._config.expected_account_id
        if expected is None:
            return

        actual = str(account.id)
        if actual != expected:
            raise RuntimeError(
                "Alpaca account identity mismatch: expected configured PAPER "
                "account was not returned"
            )

    def _latest_quote(self) -> Quote:
        request = StockLatestQuoteRequest(
            symbol_or_symbols=self._config.symbol,
            feed=self._config.feed,
        )
        quotes = cast(dict[str, Quote], self._data_client.get_stock_latest_quote(request))
        try:
            return quotes[self._config.symbol]
        except KeyError as exc:
            raise RuntimeError(
                f"No latest quote returned for configured symbol {self._config.symbol}"
            ) from exc

    def _observe_trade_updates(self) -> tuple[list[ProbeRow], ProbeRow, list[str]]:
        duration = self._config.stream_seconds
        if duration == 0:
            return (
                [],
                {
                    "status": "disabled",
                    "duration_seconds": 0.0,
                    "event_count": 0,
                },
                ["Trade update stream observation was disabled by configuration."],
            )

        updates: list[ProbeRow] = []
        warnings: list[str] = []

        async def handler(update: TradeUpdate) -> None:
            updates.append(_trade_update_row(update))

        self._trading_stream.subscribe_trade_updates(handler)
        worker = Thread(
            target=self._trading_stream.run,
            name="pytradekit-alpaca-paper-trade-updates",
            daemon=True,
        )
        worker.start()

        deadline = monotonic() + duration
        while worker.is_alive() and monotonic() < deadline:
            sleep(min(0.1, max(0.0, deadline - monotonic())))

        if worker.is_alive():
            try:
                self._trading_stream.stop()
            except Exception as exc:  # pragma: no cover - defensive SDK boundary
                warnings.append(
                    "Trading stream stop raised "
                    f"{type(exc).__name__}; no provider write was attempted."
                )

        worker.join(timeout=5.0)
        status = "window_completed" if not worker.is_alive() else "stop_timeout"

        if not updates:
            warnings.append(
                "No trade_updates event was observed. This is normal for a read-only probe "
                "when no account activity occurs during the observation window."
            )
        if worker.is_alive():
            warnings.append("Trading stream worker did not stop within five seconds.")

        return (
            updates,
            {
                "status": status,
                "duration_seconds": duration,
                "event_count": len(updates),
            },
            warnings,
        )


def build_alpaca_paper_probe(config: AlpacaPaperProbeConfig) -> AlpacaPaperReadOnlyProbe:
    """Build a probe using PAPER-only Alpaca clients.

    There is intentionally no parameter that can switch the trading clients to LIVE.
    """

    trading_client = TradingClient(
        api_key=config.api_key,
        secret_key=config.secret_key,
        paper=True,
    )
    data_client = StockHistoricalDataClient(
        api_key=config.api_key,
        secret_key=config.secret_key,
    )
    trading_stream = TradingStream(
        api_key=config.api_key,
        secret_key=config.secret_key,
        paper=True,
    )
    return AlpacaPaperReadOnlyProbe(
        config=config,
        trading_client=trading_client,
        data_client=data_client,
        trading_stream=trading_stream,
    )


def _account_row(account: TradeAccount) -> ProbeRow:
    return {
        "id": _mask_identifier(str(account.id)),
        "account_number": _mask_identifier(account.account_number),
        "status": _enum_text(account.status),
        "currency": account.currency,
        "cash": account.cash,
        "equity": account.equity,
        "buying_power": account.buying_power,
        "trading_blocked": account.trading_blocked,
        "account_blocked": account.account_blocked,
    }


def _clock_row(clock: Clock) -> ProbeRow:
    return {
        "timestamp": clock.timestamp.isoformat(),
        "is_open": clock.is_open,
        "next_open": clock.next_open.isoformat(),
        "next_close": clock.next_close.isoformat(),
    }


def _asset_row(asset: Asset) -> ProbeRow:
    return {
        "id": str(asset.id),
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_class": _enum_text(asset.asset_class),
        "exchange": _enum_text(asset.exchange),
        "status": _enum_text(asset.status),
        "tradable": asset.tradable,
        "marginable": asset.marginable,
        "shortable": asset.shortable,
        "easy_to_borrow": asset.easy_to_borrow,
        "fractionable": asset.fractionable,
        "min_order_size": _optional_text(asset.min_order_size),
        "min_trade_increment": _optional_text(asset.min_trade_increment),
        "price_increment": _optional_text(asset.price_increment),
    }


def _position_row(position: Position) -> ProbeRow:
    return {
        "asset_id": str(position.asset_id),
        "symbol": position.symbol,
        "asset_class": _enum_text(position.asset_class),
        "exchange": _enum_text(position.exchange),
        "side": _enum_text(position.side),
        "qty": position.qty,
        "qty_available": position.qty_available,
        "avg_entry_price": position.avg_entry_price,
        "market_value": position.market_value,
        "current_price": position.current_price,
    }


def _order_row(order: Order) -> ProbeRow:
    return {
        "id": str(order.id),
        "client_order_id": order.client_order_id,
        "symbol": order.symbol,
        "status": _enum_text(order.status),
        "type": _enum_text(order.type),
        "side": _enum_text(order.side),
        "time_in_force": _enum_text(order.time_in_force),
        "qty": _optional_text(order.qty),
        "filled_qty": _optional_text(order.filled_qty),
        "limit_price": _optional_text(order.limit_price),
        "stop_price": _optional_text(order.stop_price),
        "submitted_at": order.submitted_at.isoformat(),
    }


def _quote_row(quote: Quote, *, feed: DataFeed) -> ProbeRow:
    return {
        "symbol": quote.symbol,
        "feed": feed.value,
        "timestamp": quote.timestamp.isoformat(),
        "bid_price": str(quote.bid_price),
        "bid_size": str(quote.bid_size),
        "bid_exchange": _enum_text(quote.bid_exchange),
        "ask_price": str(quote.ask_price),
        "ask_size": str(quote.ask_size),
        "ask_exchange": _enum_text(quote.ask_exchange),
    }


def _trade_update_row(update: TradeUpdate) -> ProbeRow:
    order = update.order
    return {
        "event": _enum_text(update.event),
        "execution_id": _optional_text(update.execution_id),
        "timestamp": update.timestamp.isoformat(),
        "order_id": str(order.id),
        "client_order_id": order.client_order_id,
        "symbol": order.symbol,
        "order_status": _enum_text(order.status),
        "filled_qty": _optional_text(order.filled_qty),
    }


def _enum_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _mask_identifier(value: str) -> str:
    clean = value.strip()
    if len(clean) <= 4:
        return "****"
    return f"***{clean[-4:]}"
