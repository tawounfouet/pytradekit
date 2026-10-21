"""TradingHalt repository port."""

from typing import Protocol

from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.risk.domain.trading_halt import TradingHalt, TradingHaltId


class TradingHaltRepository(Protocol):
    """Persistence boundary for scoped trading halts."""

    def get(self, halt_id: TradingHaltId) -> TradingHalt | None:
        ...

    def save(self, halt: TradingHalt) -> None:
        ...

    def list_active(self) -> tuple[TradingHalt, ...]:
        ...

    def get_active(self, scope: RiskScope, scope_id: str | None) -> TradingHalt | None:
        ...
