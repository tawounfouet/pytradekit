"""TriggerTradingHalt application use case."""

from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.risk.domain.trading_halt import TradingHalt, TradingHaltId
from pytradekit.risk.ports import TradingHaltRepository
from pytradekit.runtime.ports import ClockPort


class TriggerTradingHalt:
    """Create and persist one explicit scoped trading halt."""

    def __init__(self, *, repository: TradingHaltRepository, clock: ClockPort) -> None:
        self._repository = repository
        self._clock = clock

    def execute(
        self,
        *,
        scope: RiskScope,
        scope_id: str | None,
        reason: str,
    ) -> TradingHalt:
        existing = self._repository.get_active(scope, scope_id)
        if existing is not None:
            return existing
        halt = TradingHalt(
            id=TradingHaltId.new(),
            scope=scope,
            scope_id=scope_id,
            reason=reason,
            triggered_at=self._clock.now(),
        )
        self._repository.save(halt)
        return halt
