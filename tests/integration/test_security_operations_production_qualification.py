"""Real PostgreSQL qualification for safety restart and concurrency."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from pytradekit.safety import (
    KillSwitch,
    KillSwitchId,
    KillSwitchScope,
    KillSwitchState,
    RiskOverride,
    RiskOverrideId,
    RiskOverrideScope,
)
from pytradekit.safety.adapters.postgres import (
    PostgresKillSwitchRepository,
    PostgresRiskOverrideRepository,
)
from pytradekit.safety.domain.errors import SafetyConcurrencyError
from pytradekit.security import ActorId
from pytradekit.shared import CorrelationId

NOW = datetime(2026, 10, 22, 22, 20, tzinfo=UTC)


def _switch() -> KillSwitch:
    return KillSwitch(
        id=KillSwitchId.new(),
        state=KillSwitchState.ACTIVE,
        scope=KillSwitchScope.ACCOUNT,
        environment="PAPER",
        scope_id="qualification-account",
        reason="production qualification",
        activated_by=ActorId.new(),
        activated_at=NOW,
    )


def _override() -> RiskOverride:
    actor = ActorId.new()
    return RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(
            account_id="qualification-account",
            risk_rule="MAX_ORDER_SIZE_EXCEEDED",
        ),
        reason="production qualification",
        requested_by=actor,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=10),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor, occurred_at=NOW)


def test_kill_switch_survives_committed_process_restart(
    postgres_engine: Engine,
) -> None:
    switch = _switch()
    with Session(postgres_engine, expire_on_commit=False) as first_process:
        PostgresKillSwitchRepository(first_process).save(
            switch,
            expected_version=None,
        )
        first_process.commit()

    with Session(postgres_engine) as restarted_process:
        repository = PostgresKillSwitchRepository(restarted_process)
        loaded = repository.get(switch.id)

        assert loaded == switch
        assert switch in repository.list_active()


def test_concurrent_kill_switch_release_rejects_stale_writer(
    postgres_engine: Engine,
) -> None:
    switch = _switch()
    with Session(postgres_engine, expire_on_commit=False) as seed:
        PostgresKillSwitchRepository(seed).save(switch, expected_version=None)
        seed.commit()

    first = Session(postgres_engine, expire_on_commit=False)
    second = Session(postgres_engine, expire_on_commit=False)
    try:
        first_repository = PostgresKillSwitchRepository(first)
        second_repository = PostgresKillSwitchRepository(second)
        first_loaded = first_repository.get(switch.id)
        second_loaded = second_repository.get(switch.id)
        assert first_loaded is not None
        assert second_loaded is not None

        first_release = first_loaded.release(
            actor_id=ActorId.new(),
            reason="first operator",
            occurred_at=NOW + timedelta(seconds=1),
        )
        second_release = second_loaded.release(
            actor_id=ActorId.new(),
            reason="second operator",
            occurred_at=NOW + timedelta(seconds=2),
        )

        first_repository.save(
            first_release,
            expected_version=first_loaded.version,
        )
        first.commit()

        with pytest.raises(SafetyConcurrencyError, match="Stale KillSwitch"):
            second_repository.save(
                second_release,
                expected_version=second_loaded.version,
            )
        second.rollback()
    finally:
        first.close()
        second.close()


def test_concurrent_risk_override_revoke_rejects_stale_writer(
    postgres_engine: Engine,
) -> None:
    override = _override()
    with Session(postgres_engine, expire_on_commit=False) as seed:
        PostgresRiskOverrideRepository(seed).save(
            override,
            expected_version=None,
        )
        seed.commit()

    first = Session(postgres_engine, expire_on_commit=False)
    second = Session(postgres_engine, expire_on_commit=False)
    try:
        first_repository = PostgresRiskOverrideRepository(first)
        second_repository = PostgresRiskOverrideRepository(second)
        first_loaded = first_repository.get(override.id)
        second_loaded = second_repository.get(override.id)
        assert first_loaded is not None
        assert second_loaded is not None

        first_revoke = first_loaded.revoke(
            actor_id=ActorId.new(),
            occurred_at=NOW + timedelta(seconds=1),
        )
        second_revoke = second_loaded.revoke(
            actor_id=ActorId.new(),
            occurred_at=NOW + timedelta(seconds=2),
        )

        first_repository.save(
            first_revoke,
            expected_version=first_loaded.version,
        )
        first.commit()

        with pytest.raises(SafetyConcurrencyError, match="Stale RiskOverride"):
            second_repository.save(
                second_revoke,
                expected_version=second_loaded.version,
            )
        second.rollback()
    finally:
        first.close()
        second.close()
