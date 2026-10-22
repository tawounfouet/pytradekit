"""Unit qualification for KillSwitch, RiskOverride, and confirmations."""

from datetime import UTC, datetime, timedelta

import pytest

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
    RiskOverrideStatus,
)
from pytradekit.safety.adapters import (
    InMemoryKillSwitchRepository,
    InMemoryRiskOverrideRepository,
)
from pytradekit.safety.domain.errors import SafetyConcurrencyError
from pytradekit.security import ActorId
from pytradekit.shared import CorrelationId

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


def test_kill_switch_release_increments_version_without_flatten_side_effect() -> None:
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

    released = switch.release(
        actor_id=actor_id,
        reason="recovered",
        occurred_at=NOW + timedelta(minutes=1),
    )

    assert not released.active
    assert released.version == 2
    assert released.release_reason == "recovered"


def test_stale_kill_switch_release_is_rejected() -> None:
    actor_id = ActorId.new()
    repository = InMemoryKillSwitchRepository()
    switch = KillSwitch(
        id=KillSwitchId.new(),
        state=KillSwitchState.ACTIVE,
        scope=KillSwitchScope.GLOBAL,
        reason="incident",
        activated_by=actor_id,
        activated_at=NOW,
    )
    repository.save(switch, expected_version=None)
    released = switch.release(
        actor_id=actor_id,
        reason="clear",
        occurred_at=NOW + timedelta(minutes=1),
    )
    repository.save(released, expected_version=1)

    with pytest.raises(SafetyConcurrencyError):
        repository.save(released, expected_version=1)


def test_risk_override_expires_deterministically() -> None:
    actor_id = ActorId.new()
    override = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(account_id="account-1"),
        reason="temporary exception",
        requested_by=actor_id,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=5),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor_id, occurred_at=NOW)

    assert override.status is RiskOverrideStatus.ACTIVE
    assert override.is_active(NOW + timedelta(minutes=4))
    assert not override.is_active(NOW + timedelta(minutes=5))
    assert (
        override.effective_status(NOW + timedelta(minutes=5))
        is RiskOverrideStatus.EXPIRED
    )


def test_expired_override_is_not_returned_as_active() -> None:
    actor_id = ActorId.new()
    repository = InMemoryRiskOverrideRepository()
    override = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(account_id="account-1"),
        reason="temporary exception",
        requested_by=actor_id,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(minutes=1),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor_id, occurred_at=NOW)
    repository.save(override, expected_version=None)

    assert repository.list_active(at=NOW + timedelta(seconds=30)) == (override,)
    assert repository.list_active(at=NOW + timedelta(minutes=1)) == ()


def test_confirmation_is_process_bound_and_time_bound() -> None:
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

    assert confirmation.is_valid(
        actor_id=actor_id,
        action=DangerousAction.RELEASE_KILL_SWITCH,
        scope_reference="kill-switch:1",
        at=NOW + timedelta(minutes=1),
        process_nonce="process-a",
    )
    assert not confirmation.is_valid(
        actor_id=actor_id,
        action=DangerousAction.RELEASE_KILL_SWITCH,
        scope_reference="kill-switch:1",
        at=NOW + timedelta(minutes=1),
        process_nonce="process-b",
    )
