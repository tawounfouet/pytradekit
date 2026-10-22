"""PostgreSQL Outbox and Inbox repository implementations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from pytradekit.persistence.errors import PersistenceError
from pytradekit.persistence.events import InboxRecord, InboxStatus, OutboxRecord
from pytradekit.persistence.message_models import InboxModel, OutboxModel


class PostgresOutboxRepository:
    """Transactional Outbox repository bound to one SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: OutboxRecord) -> None:
        self._session.add(
            OutboxModel(
                id=record.id,
                event_type=record.event_type,
                event_version=record.event_version,
                aggregate_type=record.aggregate_type,
                aggregate_id=record.aggregate_id,
                payload=record.payload,
                correlation_id=record.correlation_id,
                causation_id=record.causation_id,
                occurred_at=record.occurred_at,
                created_at=record.created_at,
                published_at=record.published_at,
                attempt_count=record.attempt_count,
                last_error=record.last_error,
            )
        )
        self._session.flush()

    def list_pending(self, *, limit: int = 100) -> tuple[OutboxRecord, ...]:
        if type(limit) is not int or limit <= 0:
            raise ValueError("Outbox pending limit must be a positive integer.")
        statement = (
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.created_at, OutboxModel.id)
            .limit(limit)
        )
        rows = self._session.execute(statement).scalars().all()
        return tuple(_outbox_from_model(row) for row in rows)

    def mark_published(self, record_id: UUID, *, published_at: datetime) -> None:
        row = self._session.get(OutboxModel, record_id)
        if row is None:
            raise PersistenceError(f"Outbox record {record_id} was not found.")
        row.published_at = published_at
        row.attempt_count += 1
        row.last_error = None
        self._session.flush()

    def mark_failed(self, record_id: UUID, *, error: str) -> None:
        row = self._session.get(OutboxModel, record_id)
        if row is None:
            raise PersistenceError(f"Outbox record {record_id} was not found.")
        row.attempt_count += 1
        row.last_error = _normalize_error(error)
        self._session.flush()


class PostgresInboxRepository:
    """Inbox repository using PostgreSQL uniqueness for idempotent claims."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(
        self,
        *,
        provider: str,
        external_event_id: str,
        received_at: datetime,
        payload_hash: str | None = None,
    ) -> bool:
        normalized_provider = _normalize_identity(provider, field_name="Provider")
        normalized_event_id = _normalize_identity(
            external_event_id,
            field_name="External event id",
        )
        statement = (
            insert(InboxModel)
            .values(
                provider=normalized_provider,
                external_event_id=normalized_event_id,
                received_at=received_at,
                processed_at=None,
                payload_hash=payload_hash,
                status=InboxStatus.RECEIVED.value,
            )
            .on_conflict_do_nothing(
                index_elements=["provider", "external_event_id"]
            )
            .returning(InboxModel.external_event_id)
        )
        return self._session.execute(statement).scalar_one_or_none() is not None

    def contains(self, *, provider: str, external_event_id: str) -> bool:
        statement = select(InboxModel.external_event_id).where(
            InboxModel.provider
            == _normalize_identity(provider, field_name="Provider"),
            InboxModel.external_event_id
            == _normalize_identity(
                external_event_id,
                field_name="External event id",
            ),
        )
        return self._session.execute(statement).first() is not None

    def mark_processed(
        self,
        *,
        provider: str,
        external_event_id: str,
        processed_at: datetime,
    ) -> None:
        key = (
            _normalize_identity(provider, field_name="Provider"),
            _normalize_identity(external_event_id, field_name="External event id"),
        )
        row = self._session.get(InboxModel, key)
        if row is None:
            raise PersistenceError(
                f"Inbox record {key[0]}/{key[1]} was not found."
            )
        row.status = InboxStatus.PROCESSED.value
        row.processed_at = processed_at
        self._session.flush()

    def get(
        self,
        *,
        provider: str,
        external_event_id: str,
    ) -> InboxRecord | None:
        key = (
            _normalize_identity(provider, field_name="Provider"),
            _normalize_identity(external_event_id, field_name="External event id"),
        )
        row = self._session.get(InboxModel, key)
        return _inbox_from_model(row) if row is not None else None

    def list_unprocessed(
        self,
        *,
        provider: str,
        limit: int = 100,
    ) -> tuple[InboxRecord, ...]:
        """Return durable provider events that have not reached PROCESSED."""

        if type(limit) is not int or limit <= 0:
            raise ValueError("Inbox unprocessed limit must be a positive integer.")
        normalized_provider = _normalize_identity(provider, field_name="Provider")
        statement = (
            select(InboxModel)
            .where(
                InboxModel.provider == normalized_provider,
                InboxModel.status != InboxStatus.PROCESSED.value,
            )
            .order_by(InboxModel.received_at, InboxModel.external_event_id)
            .limit(limit)
        )
        rows = self._session.execute(statement).scalars().all()
        return tuple(_inbox_from_model(row) for row in rows)


def _outbox_from_model(row: OutboxModel) -> OutboxRecord:
    return OutboxRecord(
        id=row.id,
        event_type=row.event_type,
        event_version=row.event_version,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        payload=row.payload,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        published_at=row.published_at,
        attempt_count=row.attempt_count,
        last_error=row.last_error,
    )


def _inbox_from_model(row: InboxModel) -> InboxRecord:
    return InboxRecord(
        provider=row.provider,
        external_event_id=row.external_event_id,
        received_at=row.received_at,
        processed_at=row.processed_at,
        payload_hash=row.payload_hash,
        status=InboxStatus(row.status),
    )


def _normalize_identity(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _normalize_error(error: str) -> str:
    if not isinstance(error, str) or not error.strip():
        raise ValueError("Outbox error must be a non-empty string.")
    return error.strip()[:2000]
