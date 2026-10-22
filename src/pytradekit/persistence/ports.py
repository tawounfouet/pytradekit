"""Persistence transaction contracts."""

from typing import Protocol

from pytradekit.execution.ports import FillRepository
from pytradekit.orders.ports import OrderRepository
from pytradekit.persistence.events import InboxRepository, OutboxRepository
from pytradekit.portfolio.ports import (
    AccountRepository,
    BalanceRepository,
    PositionRepository,
    ProcessedFillRegistry,
)
from pytradekit.risk.ports import RiskPolicyRepository


class TransactionBoundary(Protocol):
    """Explicit local transaction boundary."""

    def commit(self) -> None:
        """Commit the current local transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the current local transaction."""
        ...


class UnitOfWork(TransactionBoundary, Protocol):
    """Repositories participating in one local transaction."""

    orders: OrderRepository
    fills: FillRepository
    accounts: AccountRepository
    positions: PositionRepository
    balances: BalanceRepository
    processed_fills: ProcessedFillRegistry
    risk_policies: RiskPolicyRepository
    outbox: OutboxRepository
    inbox: InboxRepository
