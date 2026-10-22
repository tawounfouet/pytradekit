"""Contract qualification for in-memory persistence adapters."""

from pytradekit.execution.adapters import InMemoryFillRepository
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.portfolio.adapters import (
    InMemoryBalanceRepository,
    InMemoryPositionRepository,
    InMemoryProcessedFillRegistry,
)
from tests.contracts.repository_contracts import (
    accept_balance_repository,
    accept_fill_repository,
    accept_order_repository,
    accept_position_repository,
    accept_processed_fill_registry,
)


def test_in_memory_order_repository_contract() -> None:
    accept_order_repository(InMemoryOrderRepository())


def test_in_memory_fill_repository_contract() -> None:
    accept_fill_repository(InMemoryFillRepository())


def test_in_memory_position_repository_contract() -> None:
    accept_position_repository(InMemoryPositionRepository())


def test_in_memory_balance_repository_contract() -> None:
    accept_balance_repository(InMemoryBalanceRepository())


def test_in_memory_processed_fill_registry_contract() -> None:
    accept_processed_fill_registry(InMemoryProcessedFillRegistry())
