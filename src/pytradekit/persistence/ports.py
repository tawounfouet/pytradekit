"""Persistence transaction contracts."""

from __future__ import annotations

from typing import Protocol

from pytradekit.execution.ports import FillRepository
from pytradekit.orders.ports import OrderRepository
from pytradekit.portfolio.ports import (
    BalanceRepository,
    PositionRepository,
    ProcessedFillRegistry,
)


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
    positions: PositionRepository
    balances: BalanceRepository
    processed_fills: ProcessedFillRegistry
