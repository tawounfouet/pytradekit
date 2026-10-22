"""PostgreSQL UnitOfWork and Outbox dispatch."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from pytradekit.execution.adapters.postgres import PostgresFillRepository
from pytradekit.orders.adapters.postgres import PostgresOrderRepository
from pytradekit.persistence.events import OutboxRecord
from pytradekit.persistence.message_repositories import (
    PostgresInboxRepository,
    PostgresOutboxRepository,
)
from pytradekit.portfolio.adapters.postgres import (
    PostgresAccountRepository,
    PostgresBalanceRepository,
    PostgresPositionRepository,
    PostgresProcessedFillRegistry,
)
from pytradekit.risk.adapters.postgres import PostgresRiskPolicyRepository


class OutboxPublisher(Protocol):
    """Side-effect boundary used by the local Outbox dispatcher."""

    def publish(self, record: OutboxRecord) -> None:
        ...


class PostgresUnitOfWork:
    """One explicit local transaction over durable PyTradeKit repositories."""

    orders: PostgresOrderRepository
    fills: PostgresFillRepository
    accounts: PostgresAccountRepository
    positions: PostgresPositionRepository
    balances: PostgresBalanceRepository
    processed_fills: PostgresProcessedFillRegistry
    risk_policies: PostgresRiskPolicyRepository
    outbox: PostgresOutboxRepository
    inbox: PostgresInboxRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> PostgresUnitOfWork:
        session = self._session_factory()
        self._session = session
        self.orders = PostgresOrderRepository(session)
        self.fills = PostgresFillRepository(session)
        self.accounts = PostgresAccountRepository(session)
        self.positions = PostgresPositionRepository(session)
        self.balances = PostgresBalanceRepository(session)
        self.processed_fills = PostgresProcessedFillRegistry(session)
        self.risk_policies = PostgresRiskPolicyRepository(session)
        self.outbox = PostgresOutboxRepository(session)
        self.inbox = PostgresInboxRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if session.in_transaction():
                session.rollback()
        finally:
            session.close()
            self._session = None

    def commit(self) -> None:
        """Commit business state and Outbox records atomically."""
        self._require_session().commit()

    def rollback(self) -> None:
        """Rollback the current local transaction."""
        self._require_session().rollback()

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("PostgresUnitOfWork must be entered before use.")
        return self._session


class OutboxDispatcher:
    """Dispatch pending records with at-least-once local semantics."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], PostgresUnitOfWork],
        publisher: OutboxPublisher,
    ) -> None:
        self._uow_factory = uow_factory
        self._publisher = publisher

    def dispatch_once(self, *, limit: int = 100) -> int:
        """Publish up to limit pending records and persist dispatch outcomes."""
        published = 0
        with self._uow_factory() as uow:
            for record in uow.outbox.list_pending(limit=limit):
                try:
                    self._publisher.publish(record)
                except Exception as exc:
                    uow.outbox.mark_failed(record.id, error=str(exc) or type(exc).__name__)
                    continue
                uow.outbox.mark_published(
                    record.id,
                    published_at=record.created_at,
                )
                published += 1
            uow.commit()
        return published
