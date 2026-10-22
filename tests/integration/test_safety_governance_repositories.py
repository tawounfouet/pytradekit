"""PostgreSQL qualification for persisted safety governance state."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from pytradekit.safety import (
    DangerousAction,
    DangerousActionConfirmation,
    DangerousActionConfirmationId,
    KillSwitch,
    KillSwitchId,
    KillSwitchScope,
    KillSwitchState,
    RiskOverride,
    RiskOverrideId,
    RiskOverrideScope,
)
from pytradekit.safety.adapters.postgres import (
    PostgresDangerousActionConfirmationRepository,
    PostgresKillSwitchRepository,
    PostgresRiskOverrideRepository,
)
from pytradekit.security import ActorId
from pytradekit.shared import CorrelationId

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


def test_kill_switch_survives_repository_restart(
    postgres_session: Session,
) -> None:
    actor_id = ActorId.new()
    switch = KillSwitch(
        id=KillSwitchId.new(),
        state=KillSwitchState.ACTIVE,
        scope=KillSwitchScope.ACCOUNT,
        environment="PAPER",
        scope_id="account-1",
        reason="incident",
        activated_by=actor_id,
        activated_at=NOW,
    )
    PostgresKillSwitchRepository(postgres_session).save(
        switch,
        expected_version=None,
    )

    restarted = PostgresKillSwitchRepository(postgres_session)
    loaded = restarted.get(switch.id)

    assert loaded == switch
    assert restarted.list_active() == (switch,)


def test_risk_override_active_query_enforces_expiry(
    postgres_session: Session,
) -> None:
    actor_id = ActorId.new()
    override = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(account_id="account-1"),
        reason="temporary",
        requested_by=actor_id,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=5),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor_id, occurred_at=NOW)
    repository = PostgresRiskOverrideRepository(postgres_session)
    repository.save(override, expected_version=None)

    assert repository.list_active(at=NOW + timedelta(minutes=4)) == (override,)
    assert repository.list_active(at=NOW + timedelta(minutes=5)) == ()


def test_confirmation_does_not_restore_across_process_nonce(
    postgres_session: Session,
) -> None:
    actor_id = ActorId.new()
    confirmation = DangerousActionConfirmation(
        id=DangerousActionConfirmationId.new(),
        actor_id=actor_id,
        action=DangerousAction.RELEASE_KILL_SWITCH,
        scope_reference="kill-switch:1",
        challenge_reference="challenge-1",
        confirmed_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        process_nonce="process-a",
    )
    first = PostgresDangerousActionConfirmationRepository(
        postgres_session,
        process_nonce="process-a",
    )
    first.save(confirmation)

    restarted = PostgresDangerousActionConfirmationRepository(
        postgres_session,
        process_nonce="process-b",
    )

    assert first.get(confirmation.id) == confirmation
    assert restarted.get(confirmation.id) is None
