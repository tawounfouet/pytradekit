"""Alpaca PAPER trade-update stream and transactional event processing."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Thread

from alpaca.trading.models import TradeUpdate
from alpaca.trading.stream import TradingStream

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderStateReconciliationRequired,
)
from pytradekit.execution import ExecutionReport
from pytradekit.orders.application import HandleExecutionReport
from pytradekit.orders.domain import Order
from pytradekit.persistence import OutboxRecord
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.adapters import OrdersPortfolioEffectAdapter
from pytradekit.portfolio.application import ApplyFillToPortfolio
from pytradekit.portfolio.domain import AccountId
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import Currency

from .contract import ALPACA_PROVIDER_KEY
from .mappers import map_trade_update_report

UowFactory = Callable[[], PostgresUnitOfWork]


@dataclass(frozen=True, slots=True)
class TradeUpdateProcessingResult:
    """Outcome of one provider event processing attempt."""

    external_event_id: str
    duplicate: bool
    canonical_report_emitted: bool


class AlpacaPaperTradeStream(TradingStream):
    """Pinned Alpaca TradingStream exposing an authenticated PAPER readiness signal."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        super().__init__(
            api_key=api_key,
            secret_key=secret_key,
            paper=True,
        )
        self._pytradekit_ready = Event()

    async def _start_ws(self) -> None:
        await super()._start_ws()
        self._pytradekit_ready.set()

    async def close(self) -> None:
        self._pytradekit_ready.clear()
        await super().close()

    def wait_until_ready(self, timeout: float) -> bool:
        """Wait until Alpaca has connected, authenticated, and subscribed."""

        return self._pytradekit_ready.wait(timeout)

    @property
    def pytradekit_ready(self) -> bool:
        """Return whether the provider stream is currently authenticated."""

        return self._pytradekit_ready.is_set()


class AlpacaTradeUpdateStreamRunner:
    """Run TradingStream on one daemon thread while preserving event ordering."""

    def __init__(self, stream: AlpacaPaperTradeStream) -> None:
        self._stream = stream
        self._thread: Thread | None = None

    def start(
        self,
        handler: Callable[[TradeUpdate], TradeUpdateProcessingResult],
        *,
        timeout: float = 10.0,
    ) -> bool:
        """Start the provider stream and wait for authenticated readiness."""

        if self._thread is not None and self._thread.is_alive():
            return self._stream.wait_until_ready(timeout)

        async def on_update(update: TradeUpdate) -> None:
            await asyncio.to_thread(handler, update)

        self._stream.subscribe_trade_updates(on_update)
        self._thread = Thread(
            target=self._stream.run,
            name="pytradekit-alpaca-trade-updates",
            daemon=True,
        )
        self._thread.start()
        return self._stream.wait_until_ready(timeout)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Stop the stream and join its worker thread when running."""

        thread = self._thread
        if thread is None:
            return
        if thread.is_alive():
            self._stream.stop()
            thread.join(timeout=timeout)

    @property
    def running(self) -> bool:
        """Return whether the worker thread and authenticated stream are alive."""

        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._stream.pytradekit_ready
        )


class AlpacaTradeUpdateProcessor:
    """Process trade_updates atomically through Inbox, OMS, Portfolio, Fill, and Outbox."""

    def __init__(
        self,
        *,
        uow_factory: UowFactory,
        account_id: AccountId,
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._account_id = account_id
        self._clock = clock

    def process(self, update: TradeUpdate) -> TradeUpdateProcessingResult:
        """Process one provider event exactly once locally."""

        external_event_id = _external_event_id(update)
        payload_hash = _payload_hash(update)
        received_at = self._clock.now()
        report: ExecutionReport | None = None

        with self._uow_factory() as uow:
            claimed = uow.inbox.claim(
                provider=ALPACA_PROVIDER_KEY,
                external_event_id=external_event_id,
                received_at=received_at,
                payload_hash=payload_hash,
            )
            if not claimed:
                return TradeUpdateProcessingResult(
                    external_event_id=external_event_id,
                    duplicate=True,
                    canonical_report_emitted=False,
                )

            order = _resolve_local_order(uow, update)
            if order is None:
                raise ProviderStateReconciliationRequired(
                    "Alpaca trade_update has no durable local order mapping.",
                    provider=ALPACA_PROVIDER_KEY,
                    operation="trade_update",
                )

            if order.client_order_id is None:
                raise ProviderStateReconciliationRequired(
                    "Durable local order is missing client_order_id.",
                    provider=ALPACA_PROVIDER_KEY,
                    operation="trade_update",
                )

            context = ProviderExecutionContext(
                order_id=order.id,
                correlation_id=order.correlation_id,
                client_order_reference=order.client_order_id,
                quote_currency=Currency("USD"),
            )
            report = map_trade_update_report(update, context=context)

            if report is not None:
                fill = report.fill
                if fill is not None:
                    external_fill_id = fill.external_fill_id
                    if (
                        external_fill_id is None
                        or not uow.fills.contains_external(external_fill_id)
                    ):
                        uow.fills.add(fill)

                portfolio = OrdersPortfolioEffectAdapter(
                    ApplyFillToPortfolio(
                        positions=uow.positions,
                        balances=uow.balances,
                        processed_fills=uow.processed_fills,
                    )
                )
                HandleExecutionReport(
                    repository=uow.orders,
                    portfolio_effects=portfolio,
                ).execute(
                    report,
                    account_id=self._account_id,
                )

                uow.outbox.add(
                    _execution_outbox_record(
                        report=report,
                        occurred_at=report.occurred_at,
                    )
                )

            uow.inbox.mark_processed(
                provider=ALPACA_PROVIDER_KEY,
                external_event_id=external_event_id,
                processed_at=self._clock.now(),
            )
            uow.commit()

        return TradeUpdateProcessingResult(
            external_event_id=external_event_id,
            duplicate=False,
            canonical_report_emitted=report is not None,
        )


def _resolve_local_order(
    uow: PostgresUnitOfWork,
    update: TradeUpdate,
) -> Order | None:
    client_order_id = str(update.order.client_order_id or "").strip()
    if client_order_id:
        order = uow.orders.get_by_client_order_id(client_order_id)
        if order is not None:
            return order

    external_order_id = str(update.order.id or "").strip()
    if external_order_id:
        return uow.orders.get_by_external_order_id(external_order_id)
    return None


def _external_event_id(update: TradeUpdate) -> str:
    execution_id = str(update.execution_id or "").strip()
    if execution_id:
        return f"fill:{execution_id}"

    components = (
        str(update.order.id),
        str(update.order.client_order_id or ""),
        str(update.event),
        update.timestamp.isoformat(),
        str(update.order.status),
        str(update.order.filled_qty or ""),
    )
    digest = hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()
    return f"semantic:{digest}"


def _payload_hash(update: TradeUpdate) -> str:
    payload = update.model_dump(mode="json")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _execution_outbox_record(
    *,
    report: ExecutionReport,
    occurred_at: datetime,
) -> OutboxRecord:
    fill = report.fill
    return OutboxRecord.create(
        event_type="ExecutionReportApplied",
        aggregate_type="Order",
        aggregate_id=str(report.order_id),
        payload={
            "order_id": str(report.order_id),
            "status": report.status.value,
            "external_order_id": report.external_order_id,
            "fill_id": str(fill.id) if fill is not None else None,
            "external_fill_id": (
                fill.external_fill_id if fill is not None else None
            ),
            "fill_quantity": (
                str(fill.quantity.value) if fill is not None else None
            ),
            "fill_price": (
                str(fill.price.value) if fill is not None else None
            ),
            "fill_currency": (
                fill.price.currency.code if fill is not None else None
            ),
        },
        occurred_at=occurred_at,
        correlation_id=str(report.correlation_id),
    )
