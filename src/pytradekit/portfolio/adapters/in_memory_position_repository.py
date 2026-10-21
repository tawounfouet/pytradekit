"""In-memory PositionRepository implementation."""

from copy import deepcopy

from pytradekit.portfolio.domain import AccountId, Position
from pytradekit.shared import InstrumentId


class InMemoryPositionRepository:
    """Deterministic in-memory position store."""

    def __init__(self) -> None:
        self._positions: dict[tuple[AccountId, InstrumentId], Position] = {}

    def get(self, account_id: AccountId, instrument_id: InstrumentId) -> Position | None:
        position = self._positions.get((account_id, instrument_id))
        return deepcopy(position) if position is not None else None

    def save(self, position: Position) -> None:
        self._positions[(position.account_id, position.instrument_id)] = deepcopy(position)

    def list_for_account(self, account_id: AccountId) -> tuple[Position, ...]:
        positions = [
            deepcopy(position)
            for (stored_account_id, _), position in self._positions.items()
            if stored_account_id == account_id
        ]
        return tuple(sorted(positions, key=lambda item: str(item.instrument_id)))
