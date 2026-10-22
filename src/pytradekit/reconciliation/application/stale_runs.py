"""Crash recovery for stale reconciliation runs."""

from datetime import timedelta

from pytradekit.reconciliation.domain import ReconciliationRunId
from pytradekit.reconciliation.ports import ReconciliationRepository
from pytradekit.runtime.ports import ClockPort


class StaleRunRecovery:
    """Close abandoned active runs before starting fresh recovery."""

    def __init__(
        self,
        *,
        repository: ReconciliationRepository,
        clock: ClockPort,
        stale_after: timedelta,
    ) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive.")
        self._repository = repository
        self._clock = clock
        self._stale_after = stale_after

    def close_stale(self) -> tuple[ReconciliationRunId, ...]:
        now = self._clock.now()
        stale = self._repository.list_stale(
            stale_before=now - self._stale_after,
        )
        closed: list[ReconciliationRunId] = []
        for run in stale:
            run.fail(completed_at=now)
            self._repository.save_run(run)
            self._repository.checkpoint()
            closed.append(run.id)
        return tuple(closed)
