"""Reusable repository contract qualification helpers."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.execution.domain import Fill, FillId
from pytradekit.execution.ports import FillRepository
from pytradekit.orders import Order, OrderId, OrderSide, TimeInForce
from pytradekit.orders.ports import OrderRepository
from pytradekit.portfolio.domain import Account, AccountId, Balance, Position
from pytradekit.portfolio.ports import (
    AccountRepository,
    BalanceRepository,
    PositionRepository,
    ProcessedFillRegistry,
)
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
)

NOW = datetime(2026, 10, 22, 0, 0, tzinfo=UTC)
USD = Currency("USD")


def make_order() -> Order:
    """Build one submitted order for repository qualification."""
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("2")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    order.pull_domain_events()
    return order


def accept_order_repository(repository: OrderRepository) -> None:
    """Qualify canonical add, load and update semantics."""
    order = make_order()
    repository.add(order)

    loaded = repository.get(order.id)
    assert loaded == order
    assert loaded is not order

    loaded.accept(external_order_id="paper-order-1", occurred_at=NOW)
    loaded.pull_domain_events()
    repository.save(loaded)

    reloaded = repository.get(order.id)
    assert reloaded == loaded
    assert reloaded is not loaded


def accept_account_repository(repository: AccountRepository) -> None:
    """Qualify lossless canonical account persistence."""
    account = Account(
        id=AccountId.new(),
        base_currency=USD,
        name="paper-account",
    )
    repository.save(account)

    loaded = repository.get(account.id)
    assert loaded == account
    assert loaded is not account
    assert repository.list_all() == (account,)


def accept_fill_repository(
    repository: FillRepository,
    *,
    order_id: OrderId | None = None,
) -> None:
    """Qualify immutable fill identity and order lookup semantics."""
    order_id = order_id or OrderId.new()
    fill = Fill(
        id=FillId.new(),
        order_id=order_id,
        quantity=Quantity(Decimal("1")),
        price=Price(Decimal("100.25"), USD),
        occurred_at=NOW,
        external_fill_id="paper-fill-1",
        fee=Money(Decimal("0.01"), USD),
    )
    repository.add(fill)

    assert repository.get(fill.id) == fill
    assert repository.list_for_order(order_id) == (fill,)
    assert repository.contains_external("paper-fill-1")


def accept_position_repository(
    repository: PositionRepository,
    *,
    account_id: AccountId | None = None,
) -> None:
    """Qualify lossless position persistence."""
    account_id = account_id or AccountId.new()
    instrument_id = InstrumentId.new()
    position = Position(
        account_id=account_id,
        instrument_id=instrument_id,
        quantity=Decimal("3.5"),
        average_price=Price(Decimal("99.5"), USD),
        realized_pnl=Money(Decimal("12.25"), USD),
        opened_at=NOW,
        updated_at=NOW,
    )
    repository.save(position)

    assert repository.get(account_id, instrument_id) == position
    assert repository.list_for_account(account_id) == (position,)


def accept_balance_repository(
    repository: BalanceRepository,
    *,
    account_id: AccountId | None = None,
) -> None:
    """Qualify lossless balance persistence."""
    account_id = account_id or AccountId.new()
    balance = Balance(
        account_id=account_id,
        currency=USD,
        cash=Money(Decimal("10000.10"), USD),
        available=Money(Decimal("9000.10"), USD),
        reserved=Money(Decimal("1000"), USD),
        updated_at=NOW,
    )
    repository.save(balance)

    assert repository.get(account_id, USD) == balance
    assert repository.list_for_account(account_id) == (balance,)


def accept_processed_fill_registry(registry: ProcessedFillRegistry) -> None:
    """Qualify idempotency registry semantics."""
    assert not registry.contains("provider-fill-1")
    registry.mark("provider-fill-1")
    registry.mark("provider-fill-1")
    assert registry.contains("provider-fill-1")
