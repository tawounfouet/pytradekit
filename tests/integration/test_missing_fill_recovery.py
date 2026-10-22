"""Missing Fill recovery idempotence against real PostgreSQL."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from pytradekit.orders import Order, OrderId, OrderSide, TimeInForce
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.reconciliation import (
    BrokerSnapshot,
    CanonicalFill,
    ExternalActivityOrigin,
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
    Resolution,
    ResolutionId,
    ResolutionType,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.reconciliation.adapters.postgres import PostgresResolutionExecutor
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Quantity,
)

NOW = datetime(2026, 10, 22, 16, tzinfo=UTC)
USD = Currency("USD")


def test_same_external_fill_has_one_canonical_economic_effect(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
        client_order_id="recovery-client-1",
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    order.accept(
        external_order_id="recovery-provider-order-1",
        occurred_at=NOW,
    )
    order.pull_domain_events()

    def uow_factory() -> PostgresUnitOfWork:
        return PostgresUnitOfWork(postgres_session_factory)

    with uow_factory() as uow:
        uow.accounts.save(
            Account(
                id=account_id,
                base_currency=USD,
                name="recovery-account",
            )
        )
        uow.balances.save(
            Balance(
                account_id=account_id,
                currency=USD,
                cash=Money(Decimal("1000"), USD),
                available=Money(Decimal("1000"), USD),
                reserved=Money(Decimal("0"), USD),
                updated_at=NOW,
            )
        )
        uow.orders.add(order)
        uow.commit()

    fill_time = NOW + timedelta(seconds=1)
    canonical = CanonicalFill(
        external_fill_id="recovery-fill-1",
        order_id=order.id,
        external_order_id="recovery-provider-order-1",
        quantity=Decimal("1"),
        price=Decimal("100"),
        currency=USD,
        occurred_at=fill_time,
        origin=ExternalActivityOrigin.INTERNAL,
    )
    snapshot = BrokerSnapshot(
        account_id=account_id,
        provider="alpaca",
        orders=(),
        fills=(canonical,),
        positions=(),
        balances=(),
        captured_at=fill_time,
        watermark=SnapshotWatermark(
            captured_at=fill_time,
            provider_as_of=fill_time,
        ),
        completeness=SnapshotCompleteness.COMPLETE,
    )
    run_id = ReconciliationRunId.new()
    mismatch = Mismatch(
        id=MismatchId.new(),
        run_id=run_id,
        type=MismatchType.MISSING_INTERNAL_FILL,
        severity=MismatchSeverity.CRITICAL,
        entity_type="fill",
        entity_id=canonical.external_fill_id,
        internal_value=None,
        external_value={"external_fill_id": canonical.external_fill_id},
        detected_at=fill_time,
    )
    resolution = Resolution(
        id=ResolutionId.new(),
        run_id=run_id,
        mismatch_id=mismatch.id,
        type=ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT,
        reason="provider execution is proven",
        actor="system",
        started_at=fill_time,
        correlation_id=CorrelationId.new(),
    )
    executor = PostgresResolutionExecutor(uow_factory)

    executor.apply(
        resolution=resolution,
        mismatch=mismatch,
        broker_snapshot=snapshot,
    )
    executor.apply(
        resolution=resolution,
        mismatch=mismatch,
        broker_snapshot=snapshot,
    )

    with uow_factory() as uow:
        fills = uow.fills.list_for_order(order.id)
        position = uow.positions.get(account_id, instrument_id)
        balance = uow.balances.get(account_id, USD)
        imported = tuple(
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.event_type == "ExternalFillImported"
            and record.payload.get("external_fill_id") == canonical.external_fill_id
        )
        uow.commit()

    assert len(fills) == 1
    assert position is not None
    assert position.quantity == Decimal("1")
    assert balance is not None
    assert balance.cash.amount == Decimal("900")
    assert len(imported) == 1
