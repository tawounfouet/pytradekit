"""Dependency-free Outbox and Inbox contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    """Durable integration event waiting for dispatch."""

    id: UUID
    event_type: str
    event_version: int
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, object]
    occurred_at: datetime
    created_at: datetime
    correlation_id: str | None = None
    causation_id: str | None = None
    published_at: datetime | None = None
    attempt_count: int = 0
    last_error: str | None = None

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, object],
        occurred_at: datetime,
        event_version: int = 1,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> OutboxRecord:
        """Create a new pending outbox record."""
        return cls(
            id=uuid4(),
            event_type=event_type,
            event_version=event_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            occurred_at=occurred_at,
            created_at=datetime.now(UTC),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )


class InboxStatus(StrEnum):
    """Processing state for an external event identity."""

    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class InboxRecord:
    """Durable identity of one external provider event."""

    provider: str
    external_event_id: str
    received_at: datetime
    processed_at: datetime | None
    payload_hash: str | None
    status: InboxStatus


class OutboxRepository(Protocol):
    """Persistence contract for transactional outbox records."""

    def add(self, record: OutboxRecord) -> None:
        ...

    def list_pending(self, *, limit: int = 100) -> tuple[OutboxRecord, ...]:
        ...

    def mark_published(self, record_id: UUID, *, published_at: datetime) -> None:
        ...

    def mark_failed(self, record_id: UUID, *, error: str) -> None:
        ...


class InboxRepository(Protocol):
    """Persistence contract for external event deduplication."""

    def claim(
        self,
        *,
        provider: str,
        external_event_id: str,
        received_at: datetime,
        payload_hash: str | None = None,
    ) -> bool:
        """Return True only for the first durable claim."""
        ...

    def contains(self, *, provider: str, external_event_id: str) -> bool:
        ...

    def mark_processed(
        self,
        *,
        provider: str,
        external_event_id: str,
        processed_at: datetime,
    ) -> None:
        ...
