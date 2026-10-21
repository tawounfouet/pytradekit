"""ReleaseTradingHalt application use case."""

from pytradekit.risk.domain.trading_halt import TradingHalt, TradingHaltId
from pytradekit.risk.ports import TradingHaltRepository
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import PyTradeKitError


class ReleaseTradingHalt:
    """Release one known halt through an explicit application command."""

    def __init__(self, *, repository: TradingHaltRepository, clock: ClockPort) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, halt_id: TradingHaltId) -> TradingHalt:
        halt = self._repository.get(halt_id)
        if halt is None:
            raise PyTradeKitError(f"Trading halt {halt_id.value} was not found.")
        released = halt.release(occurred_at=self._clock.now())
        self._repository.save(released)
        return released
