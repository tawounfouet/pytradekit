"""Position repository port."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId, Position
from pytradekit.shared import InstrumentId


class PositionRepository(Protocol):
    """Persistence boundary for portfolio positions."""

    def get(self, account_id: AccountId, instrument_id: InstrumentId) -> Position | None:
        ...

    def save(self, position: Position) -> None:
        ...

    def list_for_account(self, account_id: AccountId) -> tuple[Position, ...]:
        ...
