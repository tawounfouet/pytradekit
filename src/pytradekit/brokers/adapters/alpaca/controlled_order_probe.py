"""Controlled Alpaca PAPER order probe.

The probe intentionally creates PAPER orders. It is guarded by an explicit
acknowledgement, a required expected account identity, PAPER-only clients, and a
single-attempt command client whose SDK retry counter is forced to zero.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from enum import Enum
from threading import Thread
from time import monotonic, sleep
from typing import cast
from uuid import uuid4

from alpaca.common.exceptions import APIError
from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.models.quotes import Quote
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce
from alpaca.trading.models import Asset, Clock, Order, Position, TradeAccount, TradeUpdate
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, OrderRequest
from alpaca.trading.stream import TradingStream

type ProbeScalar = str | bool | int | float | None
type ProbeRow = dict[str, ProbeScalar]

_API_KEY_ENV = "PYTRADEKIT_ALPACA_PAPER_API_KEY"
_SECRET_KEY_ENV = "PYTRADEKIT_ALPACA_PAPER_SECRET_KEY"
_EXPECTED_ACCOUNT_ENV = "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID"
_ACK_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_ACK"
_ACK_VALUE = "I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED"
_SYMBOL_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_SYMBOL"
_FEED_ENV = "PYTRADEKIT_ALPACA_DATA_FEED"
_MARKET_QTY_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_MARKET_QTY"
_LIMIT_QTY_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_LIMIT_QTY"
_LIMIT_DISCOUNT_BPS_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_LIMIT_DISCOUNT_BPS"
_ORDER_TIMEOUT_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_TIMEOUT_SECONDS"
_POLL_INTERVAL_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_POLL_SECONDS"
_STREAM_WARMUP_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_STREAM_WARMUP_SECONDS"
_STREAM_TAIL_ENV = "PYTRADEKIT_ALPACA_ORDER_PROBE_STREAM_TAIL_SECONDS"

_TERMINAL_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}


class AlpacaSimulatedResponseLoss(RuntimeError):
    """Raised after a successful PAPER submit to rehearse uncertain recovery."""


@dataclass(frozen=True, slots=True)
class AlpacaPaperOrderProbeConfig:
    """Configuration for controlled PAPER order qualification."""

    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    expected_account_id: str
    acknowledgement: str = field(repr=False)
    symbol: str = "AAPL"
    feed: DataFeed = DataFeed.IEX
    market_qty: Decimal = Decimal("0.001")
    limit_qty: Decimal = Decimal("1")
    limit_discount_bps: Decimal = Decimal("5000")
    order_timeout_seconds: float = 30.0
    poll_interval_seconds: float = 0.5
    stream_warmup_seconds: float = 2.0
    stream_tail_seconds: float = 2.0

    def __post_init__(self) -> None:
        api_key = self.api_key.strip()
        secret_key = self.secret_key.strip()
        expected = self.expected_account_id.strip()
        acknowledgement = self.acknowledgement.strip()
        symbol = self.symbol.strip().upper()

        if not api_key:
            raise ValueError(f"{_API_KEY_ENV} must be set")
        if not secret_key:
            raise ValueError(f"{_SECRET_KEY_ENV} must be set")
        if not expected:
            raise ValueError(
                f"{_EXPECTED_ACCOUNT_ENV} is required for an order-writing PAPER probe"
            )
        if acknowledgement != _ACK_VALUE:
            raise ValueError(
                f"{_ACK_ENV} must equal {_ACK_VALUE!r} before PAPER orders are created"
            )
        if not symbol:
            raise ValueError("Order probe symbol must not be empty")
        if self.market_qty <= 0:
            raise ValueError("Market quantity must be greater than zero")
        if self.limit_qty <= 0 or self.limit_qty != self.limit_qty.to_integral_value():
            raise ValueError("Limit quantity must be a positive whole-share quantity")
        if not Decimal("100") <= self.limit_discount_bps <= Decimal("9000"):
            raise ValueError("Limit discount must be between 100 and 9000 basis points")
        if self.order_timeout_seconds <= 0:
            raise ValueError("Order timeout must be greater than zero")
        if self.poll_interval_seconds <= 0:
            raise ValueError("Poll interval must be greater than zero")
        if self.stream_warmup_seconds < 0 or self.stream_tail_seconds < 0:
            raise ValueError("Stream durations must be greater than or equal to zero")

        object.__setattr__(self, "api_key", api_key)
        object.__setattr__(self, "secret_key", secret_key)
        object.__setattr__(self, "expected_account_id", expected)
        object.__setattr__(self, "acknowledgement", acknowledgement)
        object.__setattr__(self, "symbol", symbol)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> AlpacaPaperOrderProbeConfig:
        """Build the controlled PAPER config from environment variables only."""

        source = os.environ if environ is None else environ
        feed_text = source.get(_FEED_ENV, DataFeed.IEX.value).strip().lower()

        try:
            feed = DataFeed(feed_text)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in DataFeed)
            raise ValueError(f"{_FEED_ENV} must be one of: {allowed}") from exc

        return cls(
            api_key=source.get(_API_KEY_ENV, ""),
            secret_key=source.get(_SECRET_KEY_ENV, ""),
            expected_account_id=source.get(_EXPECTED_ACCOUNT_ENV, ""),
            acknowledgement=source.get(_ACK_ENV, ""),
            symbol=source.get(_SYMBOL_ENV, "AAPL"),
            feed=feed,
            market_qty=_decimal_env(source, _MARKET_QTY_ENV, "0.001"),
            limit_qty=_decimal_env(source, _LIMIT_QTY_ENV, "1"),
            limit_discount_bps=_decimal_env(source, _LIMIT_DISCOUNT_BPS_ENV, "5000"),
            order_timeout_seconds=_float_env(source, _ORDER_TIMEOUT_ENV, "30"),
            poll_interval_seconds=_float_env(source, _POLL_INTERVAL_ENV, "0.5"),
            stream_warmup_seconds=_float_env(source, _STREAM_WARMUP_ENV, "2"),
            stream_tail_seconds=_float_env(source, _STREAM_TAIL_ENV, "2"),
        )


@dataclass(frozen=True, slots=True)
class AlpacaPaperOrderProbeReport:
    """Sanitized report for one controlled PAPER order probe."""

    generated_at: str
    environment: str
    sdk_version_target: str
    result: str
    account: ProbeRow
    preflight: ProbeRow
    market_order: ProbeRow
    uncertain_recovery: ProbeRow
    limit_order: ProbeRow
    cancel: ProbeRow
    cleanup_order: ProbeRow
    baseline_position_qty: str
    final_position_qty: str
    trade_updates: list[ProbeRow]
    stream: ProbeRow
    transport_safety: ProbeRow
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "generated_at": self.generated_at,
            "environment": self.environment,
            "sdk_version_target": self.sdk_version_target,
            "result": self.result,
            "account": self.account,
            "preflight": self.preflight,
            "market_order": self.market_order,
            "uncertain_recovery": self.uncertain_recovery,
            "limit_order": self.limit_order,
            "cancel": self.cancel,
            "cleanup_order": self.cleanup_order,
            "baseline_position_qty": self.baseline_position_qty,
            "final_position_qty": self.final_position_qty,
            "trade_updates": self.trade_updates,
            "stream": self.stream,
            "transport_safety": self.transport_safety,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class AlpacaSingleAttemptTradingClient(TradingClient):
    """PAPER trading client with automatic REST retries disabled for commands."""

    def __init__(self, *, api_key: str, secret_key: str) -> None:
        super().__init__(api_key=api_key, secret_key=secret_key, paper=True)
        # alpaca-py 0.44.0 does not expose retry_attempts on TradingClient.
        # RESTClient._request reads this field before every request.
        self._retry = 0
        self._submit_attempts: dict[str, int] = {}
        self._cancel_attempts = 0

    @property
    def sdk_retry_attempts(self) -> int:
        """Return the SDK retry count enforced by this command client."""

        return self._retry

    @property
    def cancel_attempts(self) -> int:
        """Return the number of explicit cancel transport calls made."""

        return self._cancel_attempts

    def submit_attempts_for(self, client_order_id: str) -> int:
        """Return explicit submit transport attempts for one client reference."""

        return self._submit_attempts.get(client_order_id, 0)

    def submit_once(
        self,
        order_data: OrderRequest,
        *,
        simulate_response_loss: bool = False,
    ) -> Order:
        """Submit exactly once and optionally discard a successful response."""

        client_order_id = order_data.client_order_id
        if client_order_id is None:
            raise ValueError("Controlled probe orders require client_order_id")

        self._submit_attempts[client_order_id] = (
            self._submit_attempts.get(client_order_id, 0) + 1
        )
        order = cast(Order, self.submit_order(order_data))

        if simulate_response_loss:
            raise AlpacaSimulatedResponseLoss(
                "Simulated post-ack response loss after one successful PAPER submit"
            )

        return order

    def cancel_once(self, order_id: str) -> None:
        """Send one cancel request with SDK automatic retries disabled."""

        self._cancel_attempts += 1
        self.cancel_order_by_id(order_id)


class AlpacaPaperControlledOrderProbe:
    """Run bounded MARKET, LIMIT, CANCEL and recovery exercises in PAPER."""

    def __init__(
        self,
        *,
        config: AlpacaPaperOrderProbeConfig,
        read_client: TradingClient,
        command_client: AlpacaSingleAttemptTradingClient,
        data_client: StockHistoricalDataClient,
        trading_stream: TradingStream,
    ) -> None:
        self._config = config
        self._read_client = read_client
        self._command_client = command_client
        self._data_client = data_client
        self._trading_stream = trading_stream

    def run(self) -> AlpacaPaperOrderProbeReport:
        """Execute the controlled probe and return a sanitized report."""

        account = cast(TradeAccount, self._read_client.get_account())
        self._verify_expected_account(account)
        clock = cast(Clock, self._read_client.get_clock())
        if not clock.is_open:
            raise RuntimeError(
                "Alpaca market is closed. Controlled MARKET order probe requires an open market."
            )

        asset = cast(Asset, self._read_client.get_asset(self._config.symbol))
        self._validate_asset(asset)
        quote = self._latest_quote()
        baseline_qty = self._position_qty()

        updates: list[ProbeRow] = []
        warnings: list[str] = []
        errors: list[str] = []
        stream_worker = self._start_stream(updates)
        if self._config.stream_warmup_seconds:
            sleep(self._config.stream_warmup_seconds)

        market_row: ProbeRow = {}
        recovery_row: ProbeRow = {}
        limit_row: ProbeRow = {}
        cancel_row: ProbeRow = {}
        cleanup_row: ProbeRow = {}
        bought_by_probe = Decimal("0")
        market_id: str | None = None
        limit_id: str | None = None
        cleanup_id: str | None = None

        try:
            market_id = _new_client_order_id("MKT")
            market_request = MarketOrderRequest(
                symbol=self._config.symbol,
                qty=float(self._config.market_qty),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                client_order_id=market_id,
            )
            market_initial, recovery_row = self._submit_with_recovery(
                market_request,
                simulate_response_loss=True,
            )
            market_final = self._wait_for_terminal(
                market_id,
                required_status=OrderStatus.FILLED,
            )
            bought_by_probe += _order_filled_qty(market_final)
            market_row = _order_row(market_final)
            market_row["initial_status"] = _enum_text(market_initial.status)

            limit_price = self._safe_limit_price(asset=asset, quote=quote)
            limit_id = _new_client_order_id("LMT")
            limit_request = LimitOrderRequest(
                symbol=self._config.symbol,
                qty=float(self._config.limit_qty),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=float(limit_price),
                client_order_id=limit_id,
            )
            limit_initial, limit_recovery = self._submit_with_recovery(
                limit_request,
                simulate_response_loss=False,
            )
            if limit_recovery:
                warnings.append(
                    "LIMIT submit response was uncertain and recovered by client_order_id."
                )
            limit_row = _order_row(limit_initial)
            limit_row["configured_limit_price"] = str(limit_price)

            cancel_row = self._cancel_and_observe(limit_initial)
            limit_final = self._wait_for_any_terminal(limit_id)
            limit_row = _order_row(limit_final)
            limit_row["configured_limit_price"] = str(limit_price)
            bought_by_probe += _order_filled_qty(limit_final)

            if limit_final.status is not OrderStatus.CANCELED:
                errors.append(
                    "LIMIT order did not finish in CANCELED state; inspect PAPER account."
                )

        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

        if bought_by_probe > 0:
            try:
                cleanup_id = _new_client_order_id("CLEAN")
                cleanup_request = MarketOrderRequest(
                    symbol=self._config.symbol,
                    qty=float(bought_by_probe),
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                    client_order_id=cleanup_id,
                )
                cleanup_initial, cleanup_recovery = self._submit_with_recovery(
                    cleanup_request,
                    simulate_response_loss=False,
                )
                if cleanup_recovery:
                    warnings.append(
                        "Cleanup submit response was uncertain and recovered by client_order_id."
                    )
                cleanup_final = self._wait_for_terminal(
                    cleanup_id,
                    required_status=OrderStatus.FILLED,
                )
                cleanup_row = _order_row(cleanup_final)
                cleanup_row["initial_status"] = _enum_text(cleanup_initial.status)
            except Exception as exc:
                errors.append(f"Cleanup {type(exc).__name__}: {exc}")

        if self._config.stream_tail_seconds:
            sleep(self._config.stream_tail_seconds)
        stream_row = self._stop_stream(stream_worker, updates, warnings)

        final_qty = self._position_qty()
        if final_qty != baseline_qty:
            warnings.append(
                "Final PAPER position differs from baseline. "
                "Inspect the account before another probe."
            )

        safety = {
            "sdk_retry_attempts": self._command_client.sdk_retry_attempts,
            "market_submit_attempts": (
                self._command_client.submit_attempts_for(market_id)
                if market_id is not None
                else 0
            ),
            "limit_submit_attempts": (
                self._command_client.submit_attempts_for(limit_id)
                if limit_id is not None
                else 0
            ),
            "cleanup_submit_attempts": (
                self._command_client.submit_attempts_for(cleanup_id)
                if cleanup_id is not None
                else 0
            ),
            "cancel_attempts": self._command_client.cancel_attempts,
        }

        result = "PASS" if not errors and final_qty == baseline_qty else "FAIL"
        return AlpacaPaperOrderProbeReport(
            generated_at=datetime.now(UTC).isoformat(),
            environment="PAPER",
            sdk_version_target="alpaca-py==0.44.0",
            result=result,
            account=_account_row(account),
            preflight={
                "symbol": asset.symbol,
                "market_open": clock.is_open,
                "feed": self._config.feed.value,
                "market_qty": str(self._config.market_qty),
                "limit_qty": str(self._config.limit_qty),
                "quote_bid": str(quote.bid_price),
                "quote_ask": str(quote.ask_price),
            },
            market_order=market_row,
            uncertain_recovery=recovery_row,
            limit_order=limit_row,
            cancel=cancel_row,
            cleanup_order=cleanup_row,
            baseline_position_qty=str(baseline_qty),
            final_position_qty=str(final_qty),
            trade_updates=updates,
            stream=stream_row,
            transport_safety=safety,
            warnings=warnings,
            errors=errors,
        )

    def _verify_expected_account(self, account: TradeAccount) -> None:
        if str(account.id) != self._config.expected_account_id:
            raise RuntimeError(
                "Alpaca account identity mismatch: configured PAPER account was not returned"
            )
        if bool(account.trading_blocked) or bool(account.account_blocked):
            raise RuntimeError("Alpaca PAPER account is blocked for trading")

    def _validate_asset(self, asset: Asset) -> None:
        if not asset.tradable:
            raise RuntimeError(f"{asset.symbol} is not tradable")
        if (
            self._config.market_qty != self._config.market_qty.to_integral_value()
            and not asset.fractionable
        ):
            raise RuntimeError(
                f"{asset.symbol} is not fractionable but fractional MARKET qty was configured"
            )

        min_order = _optional_decimal(asset.min_order_size)
        if min_order is not None and self._config.market_qty < min_order:
            raise RuntimeError(
                f"Configured MARKET qty is below provider min_order_size {min_order}"
            )

        increment = _optional_decimal(asset.min_trade_increment)
        if increment is not None and not _aligned(self._config.market_qty, increment):
            raise RuntimeError(
                f"Configured MARKET qty does not align with provider increment {increment}"
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

    def _safe_limit_price(self, *, asset: Asset, quote: Quote) -> Decimal:
        bid = Decimal(str(quote.bid_price))
        if bid <= 0:
            raise RuntimeError("Latest bid must be positive for controlled LIMIT probe")

        factor = Decimal("1") - (self._config.limit_discount_bps / Decimal("10000"))
        raw = bid * factor
        increment = _optional_decimal(asset.price_increment) or Decimal("0.01")
        price = _floor_to_increment(raw, increment)

        if price <= 0 or price >= bid:
            raise RuntimeError("Calculated LIMIT price is not safely below the current bid")
        return price

    def _submit_with_recovery(
        self,
        request: OrderRequest,
        *,
        simulate_response_loss: bool,
    ) -> tuple[Order, ProbeRow]:
        client_order_id = request.client_order_id
        if client_order_id is None:
            raise ValueError("Controlled probe requires client_order_id")

        try:
            order = self._command_client.submit_once(
                request,
                simulate_response_loss=simulate_response_loss,
            )
            return order, {}
        except Exception as exc:
            recovered, queries = self._recover_by_client_id(client_order_id)
            return (
                recovered,
                {
                    "certainty_before_recovery": "UNCERTAIN",
                    "trigger": type(exc).__name__,
                    "simulated_post_ack_response_loss": isinstance(
                        exc, AlpacaSimulatedResponseLoss
                    ),
                    "client_order_id": client_order_id,
                    "recovery_queries": queries,
                    "recovered_order_id": str(recovered.id),
                    "recovered_status": _enum_text(recovered.status),
                    "submit_attempts": self._command_client.submit_attempts_for(
                        client_order_id
                    ),
                    "resubmitted": False,
                },
            )

    def _recover_by_client_id(self, client_order_id: str) -> tuple[Order, int]:
        deadline = monotonic() + self._config.order_timeout_seconds
        queries = 0
        last_error: Exception | None = None

        while monotonic() < deadline:
            queries += 1
            try:
                return (
                    cast(Order, self._read_client.get_order_by_client_id(client_order_id)),
                    queries,
                )
            except APIError as exc:
                last_error = exc
                if exc.status_code not in {404, None}:
                    raise
            sleep(self._config.poll_interval_seconds)

        detail = type(last_error).__name__ if last_error is not None else "not found"
        raise RuntimeError(
            f"UNCERTAIN submit unresolved for {client_order_id}; last result: {detail}"
        )

    def _wait_for_terminal(
        self,
        client_order_id: str,
        *,
        required_status: OrderStatus,
    ) -> Order:
        order = self._wait_for_any_terminal(client_order_id)
        if order.status is not required_status:
            raise RuntimeError(
                f"Order {client_order_id} reached {order.status.value}, "
                f"expected {required_status.value}"
            )
        return order

    def _wait_for_any_terminal(self, client_order_id: str) -> Order:
        deadline = monotonic() + self._config.order_timeout_seconds
        latest: Order | None = None

        while monotonic() < deadline:
            latest = cast(Order, self._read_client.get_order_by_client_id(client_order_id))
            if latest.status in _TERMINAL_STATUSES:
                return latest
            sleep(self._config.poll_interval_seconds)

        status = _enum_text(latest.status) if latest is not None else "unknown"
        raise RuntimeError(
            f"Order {client_order_id} did not reach terminal state; last status={status}"
        )

    def _cancel_and_observe(self, order: Order) -> ProbeRow:
        try:
            self._command_client.cancel_once(str(order.id))
            return {
                "requested": True,
                "provider_order_id": str(order.id),
                "transport_result": "request_returned",
            }
        except Exception as exc:
            # Do not retry cancel automatically. The subsequent order query is the
            # reconciliation path.
            return {
                "requested": True,
                "provider_order_id": str(order.id),
                "transport_result": "UNCERTAIN",
                "trigger": type(exc).__name__,
                "retried": False,
            }

    def _position_qty(self) -> Decimal:
        positions = cast(list[Position], self._read_client.get_all_positions())
        for position in positions:
            if position.symbol != self._config.symbol:
                continue
            qty = Decimal(str(position.qty))
            side = _enum_text(position.side)
            return -qty if side == "short" else qty
        return Decimal("0")

    def _start_stream(self, updates: list[ProbeRow]) -> Thread:
        async def handler(update: TradeUpdate) -> None:
            updates.append(_trade_update_row(update))

        self._trading_stream.subscribe_trade_updates(handler)
        worker = Thread(
            target=self._trading_stream.run,
            name="pytradekit-alpaca-paper-controlled-trade-updates",
            daemon=True,
        )
        worker.start()
        return worker

    def _stop_stream(
        self,
        worker: Thread,
        updates: list[ProbeRow],
        warnings: list[str],
    ) -> ProbeRow:
        if worker.is_alive():
            try:
                self._trading_stream.stop()
            except Exception as exc:  # pragma: no cover - defensive SDK boundary
                warnings.append(f"Trading stream stop raised {type(exc).__name__}.")

        worker.join(timeout=5.0)
        status = "stopped" if not worker.is_alive() else "stop_timeout"
        if worker.is_alive():
            warnings.append("Trading stream worker did not stop within five seconds.")

        return {
            "status": status,
            "event_count": len(updates),
        }


def build_alpaca_paper_order_probe(
    config: AlpacaPaperOrderProbeConfig,
) -> AlpacaPaperControlledOrderProbe:
    """Build PAPER read, command, data and stream clients for the controlled probe."""

    read_client = TradingClient(
        api_key=config.api_key,
        secret_key=config.secret_key,
        paper=True,
    )
    command_client = AlpacaSingleAttemptTradingClient(
        api_key=config.api_key,
        secret_key=config.secret_key,
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
    return AlpacaPaperControlledOrderProbe(
        config=config,
        read_client=read_client,
        command_client=command_client,
        data_client=data_client,
        trading_stream=trading_stream,
    )


def _decimal_env(source: Mapping[str, str], name: str, default: str) -> Decimal:
    value = source.get(name, default).strip()
    try:
        return Decimal(value)
    except Exception as exc:
        raise ValueError(f"{name} must be a decimal number") from exc


def _float_env(source: Mapping[str, str], name: str, default: str) -> float:
    value = source.get(name, default).strip()
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _aligned(value: Decimal, increment: Decimal) -> bool:
    if increment <= 0:
        return True
    return value % increment == 0


def _floor_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    if increment <= 0:
        raise ValueError("Price increment must be positive")
    steps = (value / increment).to_integral_value(rounding=ROUND_DOWN)
    return steps * increment


def _new_client_order_id(kind: str) -> str:
    return f"PTK45-{kind}-{uuid4().hex[:20]}"


def _order_filled_qty(order: Order) -> Decimal:
    return Decimal(str(order.filled_qty or "0"))


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
        "filled_avg_price": _optional_text(order.filled_avg_price),
        "limit_price": _optional_text(order.limit_price),
        "submitted_at": order.submitted_at.isoformat(),
    }


def _trade_update_row(update: TradeUpdate) -> ProbeRow:
    return {
        "event": _enum_text(update.event),
        "execution_id": _optional_text(update.execution_id),
        "timestamp": update.timestamp.isoformat(),
        "order_id": str(update.order.id),
        "client_order_id": update.order.client_order_id,
        "symbol": update.order.symbol,
        "order_status": _enum_text(update.order.status),
        "filled_qty": _optional_text(update.order.filled_qty),
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