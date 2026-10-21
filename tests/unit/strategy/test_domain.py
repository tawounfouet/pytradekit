from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.shared import DomainValidationError, InstrumentId
from pytradekit.strategy import (
    StrategyId,
    StrategyRun,
    StrategyRunId,
    StrategyRunStatus,
    StrategyState,
    StrategyVersion,
    TargetPosition,
)


def test_strategy_run_lifecycle_and_invalid_resume() -> None:
    run = StrategyRun(
        id=StrategyRunId.new(),
        strategy_id=StrategyId.new(),
        strategy_version=StrategyVersion("1.0.0"),
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    run.start(at=now)
    run.pause()
    run.resume()
    run.stop(at=now)
    assert run.status is StrategyRunStatus.STOPPED
    with pytest.raises(DomainValidationError):
        run.resume()


def test_strategy_state_evolves_explicitly() -> None:
    state = StrategyState.empty()
    evolved = state.evolve({"counter": 1})
    assert evolved.version == 1
    assert evolved.values["counter"] == 1
    assert state.version == 0


def test_target_position_requires_exactly_one_mode() -> None:
    instrument_id = InstrumentId.new()
    TargetPosition(instrument_id=instrument_id, target_quantity=Decimal("10"))
    with pytest.raises(DomainValidationError):
        TargetPosition(
            instrument_id=instrument_id,
            target_quantity=Decimal("10"),
            target_weight=Decimal("0.2"),
        )
