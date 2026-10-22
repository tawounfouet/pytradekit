"""LOT-09 restart and transactional trade-update qualification on PostgreSQL."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.models import TradeUpdate
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.brokers import (
    ProviderAccountIdentity,
    ProviderAccountSnapshot,
    ProviderOrderIdentity,
    ProviderOrderStateSnapshot,
    ProviderPositionSnapshot,
)
from pytradekit.brokers.adapters.alpaca.startup import (
    AlpacaStartupCoordinator,
    RemoteOpenOrder,
)
from pytradekit.brokers.adapters.alpaca.stream import (
    AlpacaTradeUpdateProcessor,
    TradeUpdateProcessingResult,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders import (
    ExecutionCertainty,
    OrderSide,
    OrderStatus,
    TimeInForce,
)
from pytradekit.orders.domain import Order, OrderId
from pytradekit.persistence import InboxStatus
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    StartupReadinessReport,
    TradingReadinessState,
)
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Quantity,
)
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 13, 0, tzinfo=UTC)
USD = Currency("USD")
PROVIDER_ACCOUNT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
PROVIDER_ORDER_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def lot09_session_factory(
    postgres_engine: Engine,
) -> Iterator[sessionmaker[Session]]:
    """Keep real UoW commits visible inside a test and rollback all state afterwards."""

    connection = postgres_engine.connect()
    outer_transaction = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
    )
    try:
        yield factory
    finally:
        outer_transaction.rollback()
        connection.close()


def _factory(
    session_factory: sessionmaker[Session],
) -> Callable[[], PostgresUnitOfWork]:
    def create() -> PostgresUnitOfWork:
        return PostgresUnitOfWork(session_factory)

    return create


def _submitted_order(*, uncertain: bool) -> Order:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    if uncertain:
        order.mark_submission_uncertain(occurred_at=NOW)
    return order


def _account_snapshot(account_id: AccountId, *, cash: str = "1000") -> ProviderAccountSnapshot:
    account = Account(
        id=account_id,
        base_currency=USD,
        name="Alpaca PAPER",
    )
    balance = Balance(
        account_id=account_id,
        currency=USD,
        cash=Money(Decimal(cash), USD),
        updated_at=NOW,
    )
    return ProviderAccountSnapshot(
        identity=ProviderAccountIdentity(
            provider="alpaca",
            external_account_id=PROVIDER_ACCOUNT_ID,
        ),
        account=account,
        cash_balance=balance,
        equity=None,
        buying_power=None,
        portfolio_value=None,
        trading_blocked=False,
        account_blocked=False,
        observed_at=NOW,
    )


class _StartupReadiness:
    def run(self) -> StartupReadinessReport:
        return StartupReadinessReport(
            provider="alpaca",
            environment="PAPER",
            account="************************eeee",
            checks=(
                ReadinessCheck(
                    name="base",
                    status=ReadinessCheckStatus.PASS,
                    detail="ok",
                ),
            ),
        )


class _Snapshots:
    def __init__(self, account: ProviderAccountSnapshot) -> None:
        self._account = account

    def get_account_snapshot(self) -> ProviderAccountSnapshot:
        return self._account

    def get_position_snapshots(self) -> tuple[ProviderPositionSnapshot, ...]:
        return ()


class _OrderReader:
    def query(self, order: Order) -> ProviderOrderStateSnapshot:
        return ProviderOrderStateSnapshot(
            order_id=order.id,
            identity=ProviderOrderIdentity(
                provider="alpaca",
                client_reference=order.client_order_id or "",
                external_order_id=PROVIDER_ORDER_ID,
            ),
            provider_status="accepted",
            canonical_status=ExecutionStatus.ACCEPTED,
            filled_quantity=Decimal("0"),
            filled_average_price=None,
            observed_at=NOW,
        )


class _OpenOrders:
    def __init__(self, client_order_id: str) -> None:
        self._client_order_id = client_order_id

    def list_open(self) -> tuple[RemoteOpenOrder, ...]:
        return (
            RemoteOpenOrder(
                external_order_id=PROVIDER_ORDER_ID,
                client_order_id=self._client_order_id,
                provider_status="accepted",
                symbol="AAPL",
            ),
        )


class _Stream:
    def __init__(self) -> None:
        self.starts = 0
        self.stops = 0

    def start(
        self,
        handler: Callable[[TradeUpdate], TradeUpdateProcessingResult],
        *,
        timeout: float = 10.0,
    ) -> bool:
        _ = handler, timeout
        self.starts += 1
        return True

    def stop(self, *, timeout: float = 5.0) -> None:
        _ = timeout
        self.stops += 1


class _NoopProcessor:
    def process(self, update: TradeUpdate) -> TradeUpdateProcessingResult:
        return TradeUpdateProcessingResult(
            external_event_id="noop",
            duplicate=False,
            canonical_report_emitted=False,
        )


def _alpaca_order(order: Order, *, status: str, filled_qty: str) -> AlpacaOrder:
    return AlpacaOrder.model_validate(
        {
            "id": PROVIDER_ORDER_ID,
            "client_order_id": order.client_order_id,
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
            "submitted_at": NOW.isoformat(),
            "symbol": "AAPL",
            "asset_class": "us_equity",
            "qty": "1",
            "filled_qty": filled_qty,
            "filled_avg_price": "100" if filled_qty != "0" else None,
            "order_class": "simple",
            "type": "market",
            "side": "buy",
            "time_in_force": "day",
            "status": status,
            "extended_hours": False,
        }
    )


def test_uncertain_order_converges_then_remains_converged_after_restart(
    lot09_session_factory: sessionmaker[Session],
) -> None:
    postgres_session_factory = lot09_session_factory
    account_id = AccountId.new()
    order = _submitted_order(uncertain=True)
    account_snapshot = _account_snapshot(account_id)

    with _factory(postgres_session_factory)() as uow:
        uow.accounts.save(account_snapshot.account)
        assert account_snapshot.cash_balance is not None
        uow.balances.save(account_snapshot.cash_balance)
        uow.orders.add(order)
        uow.commit()

    stream = _Stream()
    coordinator = AlpacaStartupCoordinator(
        startup_readiness=_StartupReadiness(),
        snapshots=_Snapshots(account_snapshot),
        order_reader=_OrderReader(),
        open_orders=_OpenOrders(order.client_order_id or ""),
        stream=stream,
        trade_updates=_NoopProcessor(),
        uow_factory=_factory(postgres_session_factory),
        account_id=account_id,
        provider_account_mask="************************eeee",
        stream_timeout=0.1,
    )

    first = coordinator.start()

    assert first.state is TradingReadinessState.TRADING_READY
    assert stream.starts == 1

    with _factory(postgres_session_factory)() as uow:
        durable = uow.orders.get(order.id)
        assert durable is not None
        assert durable.status is OrderStatus.ACCEPTED
        assert durable.execution_certainty is ExecutionCertainty.CONFIRMED
        assert durable.external_order_id == PROVIDER_ORDER_ID
        reconciliation_events = [
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.aggregate_id == str(order.id)
            and record.event_type == "OrderReconciled"
        ]
        assert len(reconciliation_events) == 1
        uow.commit()

    second_stream = _Stream()
    restarted = AlpacaStartupCoordinator(
        startup_readiness=_StartupReadiness(),
        snapshots=_Snapshots(account_snapshot),
        order_reader=_OrderReader(),
        open_orders=_OpenOrders(order.client_order_id or ""),
        stream=second_stream,
        trade_updates=_NoopProcessor(),
        uow_factory=_factory(postgres_session_factory),
        account_id=account_id,
        provider_account_mask="************************eeee",
        stream_timeout=0.1,
    ).start()

    assert restarted.state is TradingReadinessState.TRADING_READY

    with _factory(postgres_session_factory)() as uow:
        reconciliation_events = [
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.aggregate_id == str(order.id)
            and record.event_type == "OrderReconciled"
        ]
        assert len(reconciliation_events) == 1
        uow.commit()


def test_trade_update_replay_applies_one_fill_one_portfolio_effect_and_one_outbox(
    lot09_session_factory: sessionmaker[Session],
) -> None:
    postgres_session_factory = lot09_session_factory
    account_id = AccountId.new()
    order = _submitted_order(uncertain=False)
    order.accept(
        external_order_id=PROVIDER_ORDER_ID,
        occurred_at=NOW,
    )
    account_snapshot = _account_snapshot(account_id)

    with _factory(postgres_session_factory)() as uow:
        uow.accounts.save(account_snapshot.account)
        assert account_snapshot.cash_balance is not None
        uow.balances.save(account_snapshot.cash_balance)
        uow.orders.add(order)
        uow.commit()

    execution_id = uuid4()
    update = TradeUpdate.model_validate(
        {
            "event": "fill",
            "execution_id": str(execution_id),
            "order": _alpaca_order(
                order,
                status="filled",
                filled_qty="1",
            ),
            "timestamp": NOW.isoformat(),
            "position_qty": 1.0,
            "price": 100.0,
            "qty": 1.0,
        }
    )

    processor = AlpacaTradeUpdateProcessor(
        uow_factory=_factory(postgres_session_factory),
        account_id=account_id,
        clock=FakeClock.at(NOW),
    )

    first = processor.process(update)
    second = processor.process(update)

    assert first.duplicate is False
    assert first.canonical_report_emitted is True
    assert second.duplicate is True

    with _factory(postgres_session_factory)() as uow:
        durable = uow.orders.get(order.id)
        assert durable is not None
        assert durable.status is OrderStatus.FILLED
        assert durable.filled_quantity == Quantity(Decimal("1"))

        fills = uow.fills.list_for_order(order.id)
        assert len(fills) == 1
        assert fills[0].external_fill_id == str(execution_id)

        position = uow.positions.get(account_id, order.instrument_id)
        assert position is not None
        assert position.quantity == Decimal("1")
        assert position.average_price is not None
        assert position.average_price.value == Decimal("100.0")

        balance = uow.balances.get(account_id, USD)
        assert balance is not None
        assert balance.cash.amount == Decimal("900.0")

        inbox = uow.inbox.get(
            provider="alpaca",
            external_event_id=f"fill:{execution_id}",
        )
        assert inbox is not None
        assert inbox.status is InboxStatus.PROCESSED

        matching_outbox = [
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.aggregate_id == str(order.id)
            and record.event_type == "ExecutionReportApplied"
            and record.payload.get("external_fill_id") == str(execution_id)
        ]
        assert len(matching_outbox) == 1
        uow.commit()
