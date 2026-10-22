"""Alpaca PAPER startup, restart, and end-to-end reconciliation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID

from alpaca.common.exceptions import APIError
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Order as AlpacaOrder, TradeUpdate
from alpaca.trading.requests import GetOrdersRequest

from pytradekit.brokers import (
    ProviderAccountSnapshot,
    ProviderExecutionContext,
    ProviderOrderStateSnapshot,
    ProviderPositionSnapshot,
    ProviderProtocolError,
)
from pytradekit.execution import ExecutionReport, ExecutionStatus
from pytradekit.orders.application import HandleExecutionReport
from pytradekit.orders.domain import Order, OrderStatus
from pytradekit.persistence import OutboxRecord
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.domain import AccountId
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    StartupReadinessReport,
    TradingReadinessReport,
)
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import Currency

from .contract import ALPACA_PROVIDER_KEY
from .errors import AlpacaOperation, translate_alpaca_error
from .execution import AlpacaExecutionAdapter
from .mappers import map_order_state_snapshot
from .reference_resolver import StaticAlpacaReferenceResolver
from .runtime import AlpacaPaperRuntimeComposition
from .snapshots import (
    AlpacaMarketDataSnapshots,
    AlpacaSnapshotReferenceResolver,
    AlpacaSnapshotTradingClient,
    AlpacaStockDataClient,
)
from .stream import (
    AlpacaTradeUpdateProcessor,
    AlpacaTradeUpdateStreamRunner,
    TradeUpdateProcessingResult,
)

UowFactory = Callable[[], PostgresUnitOfWork]


@dataclass(frozen=True, slots=True)
class RemoteOpenOrder:
    """Minimal provider order inventory record used for startup convergence."""

    external_order_id: str
    client_order_id: str
    provider_status: str
    symbol: str


class StartupReadinessPort(Protocol):
    """LOT-05 startup gate required before full reconciliation."""

    def run(self) -> StartupReadinessReport:
        """Run configuration and infrastructure startup checks."""

        ...


class SnapshotPort(Protocol):
    """LOT-08 provider observations required by startup reconciliation."""

    def get_account_snapshot(self) -> ProviderAccountSnapshot:
        """Return current provider account state."""

        ...

    def get_position_snapshots(self) -> tuple[ProviderPositionSnapshot, ...]:
        """Return all current provider positions."""

        ...


class OrderStateReaderPort(Protocol):
    """Read one provider order as a provider-neutral state snapshot."""

    def query(self, order: Order) -> ProviderOrderStateSnapshot | None:
        """Return latest provider order state or None when not found."""

        ...


class OpenOrderInventoryPort(Protocol):
    """List all currently open provider orders for the PAPER account."""

    def list_open(self) -> tuple[RemoteOpenOrder, ...]:
        """Return provider open order inventory."""

        ...


class TradeUpdateProcessorPort(Protocol):
    """Process one private provider event through the durable local pipeline."""

    def process(self, update: TradeUpdate) -> TradeUpdateProcessingResult:
        """Process one trade update."""

        ...


class TradeStreamPort(Protocol):
    """Start and stop the authenticated private trade-update stream."""

    def start(
        self,
        handler: Callable[[TradeUpdate], TradeUpdateProcessingResult],
        *,
        timeout: float = 10.0,
    ) -> bool:
        """Start the stream and report authenticated readiness."""

        ...

    def stop(self, *, timeout: float = 5.0) -> None:
        """Stop the stream."""

        ...


class AlpacaReconciliationReadClient(Protocol):
    """Alpaca read surface required by startup order reconciliation."""

    def get_order_by_id(self, order_id: UUID | str) -> object:
        """Read provider order by provider identity."""

        ...

    def get_order_by_client_id(self, client_id: str) -> object:
        """Read provider order by client reference."""

        ...

    def get_orders(self, filter: GetOrdersRequest | None = None) -> object:
        """List provider orders."""

        ...


class AlpacaOrderStateReader:
    """Translate Alpaca order snapshots for restart reconciliation."""

    def __init__(self, client: AlpacaReconciliationReadClient) -> None:
        self._client = client

    def query(self, order: Order) -> ProviderOrderStateSnapshot | None:
        """Read one local order using provider ID first, then client reference."""

        try:
            if order.external_order_id is not None:
                response = self._client.get_order_by_id(
                    _provider_order_uuid(order.external_order_id)
                )
            else:
                client_reference = _client_reference(order)
                response = self._client.get_order_by_client_id(client_reference)
        except APIError as exc:
            if _api_status_code(exc) == 404:
                return None
            raise translate_alpaca_error(
                exc,
                operation=AlpacaOperation.READ,
            ) from exc
        except Exception as exc:
            raise translate_alpaca_error(
                exc,
                operation=AlpacaOperation.READ,
            ) from exc

        provider_order = _require_provider_order(
            response,
            operation="reconcile_order",
        )
        return map_order_state_snapshot(
            provider_order,
            context=_execution_context(order),
        )


class AlpacaOpenOrderInventory:
    """Load every open order from the dedicated Alpaca PAPER account."""

    def __init__(self, client: AlpacaReconciliationReadClient) -> None:
        self._client = client

    def list_open(self) -> tuple[RemoteOpenOrder, ...]:
        """Return a stable provider-neutral inventory of open orders."""

        try:
            response = self._client.get_orders(
                GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    limit=500,
                    nested=False,
                )
            )
        except Exception as exc:
            raise translate_alpaca_error(
                exc,
                operation=AlpacaOperation.READ,
            ) from exc

        if not isinstance(response, list):
            raise ProviderProtocolError(
                "Alpaca open-order inventory response must be a list.",
                provider=ALPACA_PROVIDER_KEY,
                operation="list_open_orders",
            )

        result: list[RemoteOpenOrder] = []
        for item in response:
            provider_order = _require_provider_order(
                item,
                operation="list_open_orders",
            )
            result.append(
                RemoteOpenOrder(
                    external_order_id=str(provider_order.id),
                    client_order_id=str(provider_order.client_order_id or ""),
                    provider_status=provider_order.status.value,
                    symbol=provider_order.symbol or "",
                )
            )

        result.sort(
            key=lambda item: (
                item.client_order_id,
                item.external_order_id,
            )
        )
        return tuple(result)


@dataclass(slots=True)
class AlpacaPaperRuntimeSystem:
    """Fully assembled LOT-09 PAPER runtime services."""

    execution: AlpacaExecutionAdapter
    snapshots: AlpacaMarketDataSnapshots
    trade_updates: AlpacaTradeUpdateProcessor
    stream: AlpacaTradeUpdateStreamRunner
    coordinator: AlpacaStartupCoordinator

    def start(self) -> TradingReadinessReport:
        """Run startup reconciliation and return full trading readiness."""

        return self.coordinator.start()

    def stop(self) -> None:
        """Stop private provider streaming."""

        self.coordinator.stop()


def build_alpaca_paper_runtime_system(
    *,
    composition: AlpacaPaperRuntimeComposition,
    mappings: Iterable[InstrumentMapping],
    account_id: AccountId,
    clock: ClockPort,
) -> AlpacaPaperRuntimeSystem:
    """Assemble LOT-05 through LOT-09 into one PAPER runtime system."""

    references = StaticAlpacaReferenceResolver(mappings)
    execution = AlpacaExecutionAdapter(
        command_client=composition.command_client,
        read_client=composition.read_client,
        instruments=references,
    )
    snapshots = AlpacaMarketDataSnapshots(
        trading_client=cast(AlpacaSnapshotTradingClient, composition.read_client),
        market_data_client=cast(AlpacaStockDataClient, composition.market_data_client),
        references=cast(AlpacaSnapshotReferenceResolver, references),
        account_id=account_id,
        expected_external_account_id=composition.profile.expected_account_id,
        clock=clock,
    )

    def uow_factory() -> PostgresUnitOfWork:
        return PostgresUnitOfWork(composition.session_factory)
    trade_updates = AlpacaTradeUpdateProcessor(
        uow_factory=uow_factory,
        account_id=account_id,
        clock=clock,
    )
    stream = AlpacaTradeUpdateStreamRunner(composition.trade_stream)
    coordinator = AlpacaStartupCoordinator(
        startup_readiness=composition.readiness,
        snapshots=snapshots,
        order_reader=AlpacaOrderStateReader(
            cast(AlpacaReconciliationReadClient, composition.read_client)
        ),
        open_orders=AlpacaOpenOrderInventory(
            cast(AlpacaReconciliationReadClient, composition.read_client)
        ),
        stream=stream,
        trade_updates=trade_updates,
        uow_factory=uow_factory,
        account_id=account_id,
        provider_account_mask=composition.profile.masked_account_id,
    )
    return AlpacaPaperRuntimeSystem(
        execution=execution,
        snapshots=snapshots,
        trade_updates=trade_updates,
        stream=stream,
        coordinator=coordinator,
    )


class AlpacaStartupCoordinator:
    """Converge durable state and provider observations before admitting trading."""

    def __init__(
        self,
        *,
        startup_readiness: StartupReadinessPort,
        snapshots: SnapshotPort,
        order_reader: OrderStateReaderPort,
        open_orders: OpenOrderInventoryPort,
        stream: TradeStreamPort,
        trade_updates: TradeUpdateProcessorPort,
        uow_factory: UowFactory,
        account_id: AccountId,
        provider_account_mask: str,
        stream_timeout: float = 10.0,
    ) -> None:
        self._startup_readiness = startup_readiness
        self._snapshots = snapshots
        self._order_reader = order_reader
        self._open_orders = open_orders
        self._stream = stream
        self._trade_updates = trade_updates
        self._uow_factory = uow_factory
        self._account_id = account_id
        self._provider_account_mask = provider_account_mask
        self._stream_timeout = stream_timeout

    def start(self) -> TradingReadinessReport:
        """Run two-phase reconciliation around stream startup."""

        checks: list[ReadinessCheck] = []
        gaps: list[str] = []

        startup = self._startup_readiness.run()
        if not startup.ready_for_startup:
            checks.append(
                ReadinessCheck(
                    name="startup_prerequisites",
                    status=ReadinessCheckStatus.FAIL,
                    detail="LOT-05 startup prerequisites are not satisfied.",
                )
            )
            return self._report(checks, gaps)

        checks.append(
            ReadinessCheck(
                name="startup_prerequisites",
                status=ReadinessCheckStatus.PASS,
                detail="LOT-05 startup prerequisites passed.",
            )
        )

        pre_stream_gaps = self._reconcile_cycle()
        gaps.extend(pre_stream_gaps)
        checks.append(
            _gap_check(
                "pre_stream_reconciliation",
                pre_stream_gaps,
                success="Durable state and provider snapshots converged before stream startup.",
            )
        )
        if pre_stream_gaps:
            return self._report(checks, gaps)

        stream_ready = self._stream.start(
            self._trade_updates.process,
            timeout=self._stream_timeout,
        )
        checks.append(
            ReadinessCheck(
                name="trade_updates_stream",
                status=(
                    ReadinessCheckStatus.PASS
                    if stream_ready
                    else ReadinessCheckStatus.FAIL
                ),
                detail=(
                    "Alpaca trade_updates authenticated and subscribed."
                    if stream_ready
                    else "Alpaca trade_updates did not become ready."
                ),
            )
        )
        if not stream_ready:
            gaps.append("trade_updates stream is not ready")
            return self._report(checks, gaps)

        post_stream_gaps = self._reconcile_cycle()
        gaps.extend(post_stream_gaps)
        checks.append(
            _gap_check(
                "post_stream_reconciliation",
                post_stream_gaps,
                success=(
                    "Second reconciliation closed the snapshot-to-stream race window."
                ),
            )
        )

        inbox_gaps, pending_outbox = self._message_state()
        gaps.extend(inbox_gaps)
        checks.append(
            _gap_check(
                "inbox",
                inbox_gaps,
                success="No unprocessed Alpaca Inbox records remain.",
            )
        )
        checks.append(
            ReadinessCheck(
                name="outbox",
                status=ReadinessCheckStatus.PASS,
                detail=(
                    f"{pending_outbox} durable Outbox record(s) await at-least-once dispatch."
                ),
            )
        )

        return self._report(checks, gaps)

    def stop(self) -> None:
        """Stop the provider stream."""

        self._stream.stop()

    def _reconcile_cycle(self) -> list[str]:
        gaps: list[str] = []
        account = self._snapshots.get_account_snapshot()
        positions = self._snapshots.get_position_snapshots()
        gaps.extend(self._reconcile_portfolio(account, positions))
        gaps.extend(self._reconcile_local_orders())
        gaps.extend(self._reconcile_remote_open_orders())
        return gaps

    def _reconcile_portfolio(
        self,
        provider_account: ProviderAccountSnapshot,
        provider_positions: tuple[ProviderPositionSnapshot, ...],
    ) -> list[str]:
        gaps: list[str] = []

        if provider_account.account.id != self._account_id:
            return ["provider account snapshot uses the wrong canonical AccountId"]

        with self._uow_factory() as uow:
            local_account = uow.accounts.get(self._account_id)
            if local_account is None:
                uow.accounts.save(provider_account.account)
                local_account = provider_account.account
            elif local_account.base_currency != provider_account.account.base_currency:
                gaps.append("local account currency differs from Alpaca")

            provider_balance = provider_account.cash_balance
            if provider_balance is not None:
                local_balance = uow.balances.get(
                    self._account_id,
                    provider_balance.currency,
                )
                if local_balance is None:
                    uow.balances.save(provider_balance)
                elif local_balance.cash != provider_balance.cash:
                    gaps.append("local cash balance differs from Alpaca")

            local_positions = {
                position.instrument_id: position
                for position in uow.positions.list_for_account(self._account_id)
            }
            provider_by_instrument = {
                snapshot.instrument_id: snapshot
                for snapshot in provider_positions
            }

            for instrument_id, provider_position in provider_by_instrument.items():
                local_position = local_positions.get(instrument_id)
                if local_position is None:
                    gaps.append(
                        f"provider position {instrument_id} has no durable local position"
                    )
                    continue
                if local_position.quantity != provider_position.signed_quantity:
                    gaps.append(
                        f"position quantity mismatch for {instrument_id}"
                    )
                    continue
                local_average = (
                    local_position.average_price.value
                    if local_position.average_price is not None
                    else None
                )
                if local_average != provider_position.average_price.value:
                    gaps.append(
                        f"position average price mismatch for {instrument_id}"
                    )

            for instrument_id, local_position in local_positions.items():
                if (
                    local_position.quantity != Decimal("0")
                    and instrument_id not in provider_by_instrument
                ):
                    gaps.append(
                        f"durable position {instrument_id} is absent from Alpaca"
                    )

            uow.commit()

        return gaps

    def _reconcile_local_orders(self) -> list[str]:
        gaps: list[str] = []

        with self._uow_factory() as uow:
            local_orders = uow.orders.list_reconcilable()
            uow.commit()

        for order in local_orders:
            if order.status in {OrderStatus.CREATED, OrderStatus.VALIDATED}:
                gaps.append(
                    f"local order {order.id} is pre-submission and requires operator decision"
                )
                continue

            snapshot = self._order_reader.query(order)
            if snapshot is None:
                gaps.append(
                    f"local order {order.id} is not currently observable at Alpaca"
                )
                continue

            gap = self._converge_one_order(order, snapshot)
            if gap is not None:
                gaps.append(gap)

        return gaps

    def _converge_one_order(
        self,
        order: Order,
        snapshot: ProviderOrderStateSnapshot,
    ) -> str | None:
        status = snapshot.canonical_status
        if status is None:
            return (
                f"provider order state {snapshot.provider_status} for {order.id} "
                "requires explicit reconciliation"
            )

        if snapshot.identity.client_reference != order.client_order_id:
            return f"client order reference mismatch for {order.id}"

        if (
            order.external_order_id is not None
            and snapshot.identity.external_order_id != order.external_order_id
        ):
            return f"provider order identity mismatch for {order.id}"

        if status in {
            ExecutionStatus.PARTIALLY_FILLED,
            ExecutionStatus.FILLED,
        }:
            if snapshot.filled_quantity != order.filled_quantity.value:
                return (
                    f"provider fill quantity differs from durable quantity for {order.id}"
                )
            if (
                status is ExecutionStatus.PARTIALLY_FILLED
                and order.status is OrderStatus.PARTIALLY_FILLED
                and not order.cancel_requested
            ):
                return None
            if status is ExecutionStatus.FILLED and order.status is OrderStatus.FILLED:
                return None
            return (
                f"provider fill state for {order.id} requires missing execution facts"
            )

        if status is ExecutionStatus.ACCEPTED:
            if order.status is OrderStatus.ACCEPTED and not order.cancel_requested:
                return None
            if order.status is not OrderStatus.SUBMITTED:
                return f"provider acceptance conflicts with local state for {order.id}"

        if status is ExecutionStatus.CANCELLED:
            cancellable_confirmation = (
                order.status is OrderStatus.CANCEL_REQUESTED
                or (
                    order.status is OrderStatus.PARTIALLY_FILLED
                    and order.cancel_requested
                )
            )
            if not cancellable_confirmation:
                return (
                    f"provider cancellation for {order.id} has no local cancel request"
                )

        if status is ExecutionStatus.REJECTED and order.status is not OrderStatus.SUBMITTED:
            return f"provider rejection conflicts with local state for {order.id}"

        report = ExecutionReport(
            order_id=order.id,
            status=status,
            occurred_at=snapshot.observed_at,
            correlation_id=order.correlation_id,
            external_order_id=snapshot.identity.external_order_id,
            rejection_reason=(
                "Alpaca reported order rejection during startup reconciliation."
                if status is ExecutionStatus.REJECTED
                else None
            ),
        )

        with self._uow_factory() as uow:
            HandleExecutionReport(repository=uow.orders).execute(report)
            uow.outbox.add(
                _reconciliation_outbox_record(report)
            )
            uow.commit()

        return None

    def _reconcile_remote_open_orders(self) -> list[str]:
        gaps: list[str] = []
        remote_orders = self._open_orders.list_open()

        with self._uow_factory() as uow:
            for remote in remote_orders:
                if not remote.client_order_id.strip():
                    gaps.append(
                        (
                            "Alpaca PAPER account contains an open order without "
                            f"client_order_id: {remote.external_order_id}"
                        )
                    )
                    continue
                local = uow.orders.get_by_client_order_id(remote.client_order_id)
                if local is None:
                    gaps.append(
                        (
                            "Alpaca PAPER account contains an open order with no "
                            f"durable local match: {remote.external_order_id}"
                        )
                    )
                    continue
                if local.is_terminal:
                    gaps.append(
                        f"terminal local order {local.id} is still open at Alpaca"
                    )
                    continue
                if (
                    local.external_order_id is not None
                    and local.external_order_id != remote.external_order_id
                ):
                    gaps.append(
                        f"remote open-order identity mismatch for {local.id}"
                    )
            uow.commit()

        return gaps

    def _message_state(self) -> tuple[list[str], int]:
        with self._uow_factory() as uow:
            unprocessed = uow.inbox.list_unprocessed(
                provider=ALPACA_PROVIDER_KEY,
                limit=100,
            )
            pending_outbox = len(uow.outbox.list_pending(limit=100))
            uow.commit()

        gaps = [
            f"unprocessed Inbox event {record.external_event_id}"
            for record in unprocessed
        ]
        return gaps, pending_outbox

    def _report(
        self,
        checks: list[ReadinessCheck],
        gaps: list[str],
    ) -> TradingReadinessReport:
        return TradingReadinessReport(
            provider=ALPACA_PROVIDER_KEY,
            environment="PAPER",
            account=self._provider_account_mask,
            checks=tuple(checks),
            gaps=tuple(dict.fromkeys(gaps)),
        )


def _gap_check(
    name: str,
    gaps: list[str],
    *,
    success: str,
) -> ReadinessCheck:
    return ReadinessCheck(
        name=name,
        status=(
            ReadinessCheckStatus.FAIL if gaps else ReadinessCheckStatus.PASS
        ),
        detail=(
            f"{len(gaps)} reconciliation gap(s) remain."
            if gaps
            else success
        ),
    )


def _execution_context(order: Order) -> ProviderExecutionContext:
    return ProviderExecutionContext(
        order_id=order.id,
        correlation_id=order.correlation_id,
        client_order_reference=_client_reference(order),
        quote_currency=Currency("USD"),
    )


def _client_reference(order: Order) -> str:
    value = order.client_order_id
    if value is None or not value.strip():
        raise ProviderProtocolError(
            "Durable order is missing client_order_id.",
            provider=ALPACA_PROVIDER_KEY,
            operation="reconcile_order",
        )
    return value.strip()


def _provider_order_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ProviderProtocolError(
            "Alpaca external order ID must be a UUID.",
            provider=ALPACA_PROVIDER_KEY,
            operation="reconcile_order",
        ) from exc


def _require_provider_order(value: object, *, operation: str) -> AlpacaOrder:
    if not isinstance(value, AlpacaOrder):
        raise ProviderProtocolError(
            "Alpaca order query returned an unexpected payload type.",
            provider=ALPACA_PROVIDER_KEY,
            operation=operation,
        )
    return value


def _api_status_code(error: APIError) -> int | None:
    try:
        value: object = error.status_code
    except Exception:
        return None
    return value if isinstance(value, int) else None


def _reconciliation_outbox_record(report: ExecutionReport) -> OutboxRecord:
    return OutboxRecord.create(
        event_type="OrderReconciled",
        aggregate_type="Order",
        aggregate_id=str(report.order_id),
        payload={
            "order_id": str(report.order_id),
            "status": report.status.value,
            "external_order_id": report.external_order_id,
        },
        occurred_at=report.occurred_at,
        correlation_id=str(report.correlation_id),
    )
