"""Production crash-window qualification for Alpaca trade_update processing."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.models import TradeUpdate
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.brokers.adapters.alpaca.stream import AlpacaTradeUpdateProcessor
from pytradekit.orders import OrderSide, OrderStatus, TimeInForce
from pytradekit.orders.domain import Order, OrderId
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.runtime.faults import (
    FaultPoint,
    InjectedRuntimeFault,
    OneShotFaultInjector,
)
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Quantity,
)
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)
USD = Currency("USD")


@pytest.fixture
def fault_session_factory(
    postgres_engine: Engine,
) -> Iterator[sessionmaker[Session]]:
    """Allow real UoW commits while rolling back all test state at the end."""

    connection = postgres_engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield factory
    finally:
        outer.rollback()
        connection.close()


def _uow_factory(
    factory: sessionmaker[Session],
) -> Callable[[], PostgresUnitOfWork]:
    return lambda: PostgresUnitOfWork(factory)


def _accepted_order(provider_order_id: str) -> Order:
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
    order.accept(
        external_order_id=provider_order_id,
        occurred_at=NOW,
    )
    return order


def _seed(
    factory: sessionmaker[Session],
    *,
    account_id: AccountId,
    order: Order,
) -> None:
    with PostgresUnitOfWork(factory) as uow:
        uow.accounts.save(
            Account(
                id=account_id,
                base_currency=USD,
                name="PAPER qualification",
            )
        )
        uow.balances.save(
            Balance(
                account_id=account_id,
                currency=USD,
                cash=Money(Decimal("1000"), USD),
                updated_at=NOW,
            )
        )
        uow.orders.add(order)
        uow.commit()


def _trade_update(
    order: Order,
    *,
    provider_order_id: str,
    execution_id: UUID,
) -> TradeUpdate:
    provider_order = AlpacaOrder.model_validate(
        {
            "id": provider_order_id,
            "client_order_id": order.client_order_id,
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
            "submitted_at": NOW.isoformat(),
            "symbol": "AAPL",
            "asset_class": "us_equity",
            "qty": "1",
            "filled_qty": "1",
            "filled_avg_price": "100",
            "order_class": "simple",
            "type": "market",
            "side": "buy",
            "time_in_force": "day",
            "status": "filled",
            "extended_hours": False,
        }
    )
    return TradeUpdate.model_validate(
        {
            "event": "fill",
            "execution_id": str(execution_id),
            "order": provider_order,
            "timestamp": NOW.isoformat(),
            "position_qty": 1.0,
            "price": 100.0,
            "qty": 1.0,
        }
    )


def _assert_not_applied(
    factory: sessionmaker[Session],
    *,
    account_id: AccountId,
    order: Order,
    execution_id: UUID,
) -> None:
    with PostgresUnitOfWork(factory) as uow:
        durable = uow.orders.get(order.id)
        assert durable is not None
        assert durable.status is OrderStatus.ACCEPTED
        assert durable.filled_quantity == Quantity(Decimal("0"))
        assert uow.fills.list_for_order(order.id) == ()
        assert uow.positions.get(account_id, order.instrument_id) is None

        balance = uow.balances.get(account_id, USD)
        assert balance is not None
        assert balance.cash.amount == Decimal("1000")

        assert (
            uow.inbox.get(
                provider="alpaca",
                external_event_id=f"fill:{execution_id}",
            )
            is None
        )
        matching = [
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.aggregate_id == str(order.id)
        ]
        assert matching == []
        uow.commit()


def _assert_applied_once(
    factory: sessionmaker[Session],
    *,
    account_id: AccountId,
    order: Order,
    execution_id: UUID,
) -> None:
    with PostgresUnitOfWork(factory) as uow:
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

        balance = uow.balances.get(account_id, USD)
        assert balance is not None
        assert balance.cash.amount == Decimal("900.0")

        inbox = uow.inbox.get(
            provider="alpaca",
            external_event_id=f"fill:{execution_id}",
        )
        assert inbox is not None
        assert inbox.processed_at is not None

        matching = [
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.aggregate_id == str(order.id)
            and record.payload.get("external_fill_id") == str(execution_id)
        ]
        assert len(matching) == 1
        uow.commit()


@pytest.mark.parametrize(
    "fault_point",
    [
        FaultPoint.BEFORE_INBOX_CLAIM,
        FaultPoint.AFTER_INBOX_CLAIM,
        FaultPoint.AFTER_FILL_PERSIST,
        FaultPoint.AFTER_CANONICAL_APPLY,
        FaultPoint.AFTER_OUTBOX_ADD,
        FaultPoint.BEFORE_COMMIT,
    ],
)
def test_every_precommit_crash_window_rolls_back_then_replays_once(
    fault_session_factory: sessionmaker[Session],
    fault_point: FaultPoint,
) -> None:
    account_id = AccountId.new()
    provider_order_id = str(uuid4())
    execution_id = uuid4()
    order = _accepted_order(provider_order_id)
    _seed(
        fault_session_factory,
        account_id=account_id,
        order=order,
    )
    update = _trade_update(
        order,
        provider_order_id=provider_order_id,
        execution_id=execution_id,
    )

    crashing = AlpacaTradeUpdateProcessor(
        uow_factory=_uow_factory(fault_session_factory),
        account_id=account_id,
        clock=FakeClock.at(NOW),
        faults=OneShotFaultInjector(fault_point),
    )

    with pytest.raises(InjectedRuntimeFault, match=fault_point.value):
        crashing.process(update)

    _assert_not_applied(
        fault_session_factory,
        account_id=account_id,
        order=order,
        execution_id=execution_id,
    )

    replay = AlpacaTradeUpdateProcessor(
        uow_factory=_uow_factory(fault_session_factory),
        account_id=account_id,
        clock=FakeClock.at(NOW),
    )
    result = replay.process(update)

    assert result.duplicate is False
    _assert_applied_once(
        fault_session_factory,
        account_id=account_id,
        order=order,
        execution_id=execution_id,
    )


def test_crash_after_commit_keeps_one_effect_and_replay_is_duplicate(
    fault_session_factory: sessionmaker[Session],
) -> None:
    account_id = AccountId.new()
    provider_order_id = str(uuid4())
    execution_id = uuid4()
    order = _accepted_order(provider_order_id)
    _seed(
        fault_session_factory,
        account_id=account_id,
        order=order,
    )
    update = _trade_update(
        order,
        provider_order_id=provider_order_id,
        execution_id=execution_id,
    )

    crashing = AlpacaTradeUpdateProcessor(
        uow_factory=_uow_factory(fault_session_factory),
        account_id=account_id,
        clock=FakeClock.at(NOW),
        faults=OneShotFaultInjector(FaultPoint.AFTER_COMMIT),
    )

    with pytest.raises(InjectedRuntimeFault, match="after_commit"):
        crashing.process(update)

    _assert_applied_once(
        fault_session_factory,
        account_id=account_id,
        order=order,
        execution_id=execution_id,
    )

    replay = AlpacaTradeUpdateProcessor(
        uow_factory=_uow_factory(fault_session_factory),
        account_id=account_id,
        clock=FakeClock.at(NOW),
    )
    result = replay.process(update)

    assert result.duplicate is True
    _assert_applied_once(
        fault_session_factory,
        account_id=account_id,
        order=order,
        execution_id=execution_id,
    )
