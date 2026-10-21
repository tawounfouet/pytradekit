"""In-memory TradingHaltRepository implementation."""

from copy import deepcopy

from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.risk.domain.trading_halt import TradingHalt, TradingHaltId


class InMemoryTradingHaltRepository:
    """Deterministic in-memory scoped halt store."""

    def __init__(self) -> None:
        self._halts: dict[TradingHaltId, TradingHalt] = {}

    def get(self, halt_id: TradingHaltId) -> TradingHalt | None:
        halt = self._halts.get(halt_id)
        return deepcopy(halt) if halt is not None else None

    def save(self, halt: TradingHalt) -> None:
        self._halts[halt.id] = deepcopy(halt)

    def list_active(self) -> tuple[TradingHalt, ...]:
        active = [deepcopy(halt) for halt in self._halts.values() if halt.active]
        return tuple(sorted(active, key=lambda item: str(item.id.value)))

    def get_active(self, scope: RiskScope, scope_id: str | None) -> TradingHalt | None:
        for halt in self._halts.values():
            if halt.active and halt.scope is scope and halt.scope_id == scope_id:
                return deepcopy(halt)
        return None
