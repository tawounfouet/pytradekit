"""Transaction, Outbox, and Inbox qualification on real PostgreSQL."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.orders.adapters.postgres.models import OrderModel
from pytradekit.persistence.events import InboxStatus, OutboxRecord
from pytradekit.persistence.message_models import OutboxModel
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from tests.contracts.repository_contracts import make_order

NOW = datetime(2026, 10, 22, 0, 30, tzinfo=UTC)


def _uow_factory(
    factory: sessionmaker[Session],
) -> PostgresUnitOfWork:
    return PostgresUnitOfWork(factory)


def test_business_state_and_outbox_rollback_together(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    order = make_order()
    record = OutboxRecord.create(
        event_type="OrderSubmitted",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        payload={"order_id": str(order.id)},
        occurred_at=NOW,
    )

    try:
        with _uow_factory(postgres_session_factory) as uow:
            uow.orders.add(order)
            uow.outbox.add(record)
            raise RuntimeError("synthetic crash before commit")
    except RuntimeError:
        pass

    with postgres_session_factory() as session:
        assert session.get(OrderModel, order.id.value) is None
        assert session.get(OutboxModel, record.id) is None


def test_business_state_and_outbox_are_durable_after_commit(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    order = make_order()
    record = OutboxRecord.create(
        event_type="OrderSubmitted",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        payload={"order_id": str(order.id)},
        occurred_at=NOW,
    )

    with _uow_factory(postgres_session_factory) as uow:
        uow.orders.add(order)
        uow.outbox.add(record)
        uow.commit()

    with postgres_session_factory() as session:
        assert session.get(OrderModel, order.id.value) is not None
        assert session.get(OutboxModel, record.id) is not None


def test_same_external_event_is_claimed_once(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    with _uow_factory(postgres_session_factory) as uow:
        first = uow.inbox.claim(
            provider="alpaca",
            external_event_id="event-duplicate-1",
            received_at=NOW,
            payload_hash="abc123",
        )
        second = uow.inbox.claim(
            provider="alpaca",
            external_event_id="event-duplicate-1",
            received_at=NOW,
            payload_hash="abc123",
        )
        uow.inbox.mark_processed(
            provider="alpaca",
            external_event_id="event-duplicate-1",
            processed_at=NOW,
        )
        uow.commit()

    assert first is True
    assert second is False

    with _uow_factory(postgres_session_factory) as uow:
        record = uow.inbox.get(
            provider="alpaca",
            external_event_id="event-duplicate-1",
        )
        assert record is not None
        assert record.status is InboxStatus.PROCESSED


def test_pending_outbox_record_survives_dispatch_failure(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    record = OutboxRecord.create(
        event_type="QualificationEvent",
        aggregate_type="Test",
        aggregate_id="qualification-1",
        payload={"ok": True},
        occurred_at=NOW,
    )
    with _uow_factory(postgres_session_factory) as uow:
        uow.outbox.add(record)
        uow.commit()

    with _uow_factory(postgres_session_factory) as uow:
        uow.outbox.mark_failed(record.id, error="synthetic dispatch failure")
        uow.commit()

    with postgres_session_factory() as session:
        row = session.execute(
            select(OutboxModel).where(OutboxModel.id == record.id)
        ).scalar_one()
        assert row.published_at is None
        assert row.attempt_count == 1
        assert row.last_error == "synthetic dispatch failure"
