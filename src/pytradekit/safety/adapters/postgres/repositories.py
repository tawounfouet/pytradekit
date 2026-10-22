"""PostgreSQL repositories for Safety governance."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from pytradekit.safety.adapters.postgres.models import (
    DangerousActionConfirmationModel,
    KillSwitchModel,
    RiskOverrideModel,
)
from pytradekit.safety.domain import (
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
from pytradekit.safety.domain.errors import SafetyConcurrencyError
from pytradekit.security.domain import ActorId
from pytradekit.shared import CorrelationId


class PostgresKillSwitchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, switch_id: KillSwitchId) -> KillSwitch | None:
        row = self._session.get(KillSwitchModel, switch_id.value)
        return self._from_model(row) if row is not None else None

    def list_active(self) -> tuple[KillSwitch, ...]:
        statement = (
            select(KillSwitchModel)
            .where(KillSwitchModel.state == KillSwitchState.ACTIVE.value)
            .order_by(KillSwitchModel.activated_at, KillSwitchModel.id)
        )
        return tuple(
            self._from_model(row)
            for row in self._session.execute(statement).scalars().all()
        )

    def save(
        self,
        switch: KillSwitch,
        *,
        expected_version: int | None,
    ) -> None:
        row = self._session.get(KillSwitchModel, switch.id.value)
        values = self._values(switch)
        if row is None:
            if expected_version is not None:
                raise SafetyConcurrencyError("KillSwitch does not yet exist.")
            self._session.add(KillSwitchModel(**values))
            self._session.flush()
            return

        if expected_version is None:
            raise SafetyConcurrencyError("KillSwitch update requires expected_version.")
        statement = (
            update(KillSwitchModel)
            .where(
                KillSwitchModel.id == switch.id.value,
                KillSwitchModel.version == expected_version,
            )
            .values(**{key: value for key, value in values.items() if key != "id"})
        )
        result = cast(CursorResult[Any], self._session.execute(statement))
        if result.rowcount != 1:
            raise SafetyConcurrencyError("Stale KillSwitch version.")
        self._session.flush()

    @staticmethod
    def _values(switch: KillSwitch) -> dict[str, object]:
        return {
            "id": switch.id.value,
            "state": switch.state.value,
            "scope": switch.scope.value,
            "environment": switch.environment,
            "scope_id": switch.scope_id,
            "reason": switch.reason,
            "activated_by": switch.activated_by.value,
            "activated_at": switch.activated_at,
            "released_by": (
                switch.released_by.value if switch.released_by is not None else None
            ),
            "released_at": switch.released_at,
            "release_reason": switch.release_reason,
            "version": switch.version,
        }

    @staticmethod
    def _from_model(row: KillSwitchModel) -> KillSwitch:
        return KillSwitch(
            id=KillSwitchId(row.id),
            state=KillSwitchState(row.state),
            scope=KillSwitchScope(row.scope),
            environment=row.environment,
            scope_id=row.scope_id,
            reason=row.reason,
            activated_by=ActorId(row.activated_by),
            activated_at=row.activated_at,
            released_by=(
                ActorId(row.released_by) if row.released_by is not None else None
            ),
            released_at=row.released_at,
            release_reason=row.release_reason,
            version=row.version,
        )


class PostgresRiskOverrideRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, override_id: RiskOverrideId) -> RiskOverride | None:
        row = self._session.get(RiskOverrideModel, override_id.value)
        return self._from_model(row) if row is not None else None

    def list_active(self, *, at: datetime) -> tuple[RiskOverride, ...]:
        statement = (
            select(RiskOverrideModel)
            .where(
                RiskOverrideModel.status == RiskOverrideStatus.ACTIVE.value,
                RiskOverrideModel.valid_from <= at,
                RiskOverrideModel.valid_until > at,
            )
            .order_by(RiskOverrideModel.valid_until, RiskOverrideModel.id)
        )
        return tuple(
            self._from_model(row)
            for row in self._session.execute(statement).scalars().all()
        )

    def save(
        self,
        override: RiskOverride,
        *,
        expected_version: int | None,
    ) -> None:
        row = self._session.get(RiskOverrideModel, override.id.value)
        values = self._values(override)
        if row is None:
            if expected_version is not None:
                raise SafetyConcurrencyError("RiskOverride does not yet exist.")
            self._session.add(RiskOverrideModel(**values))
            self._session.flush()
            return

        if expected_version is None:
            raise SafetyConcurrencyError("RiskOverride update requires expected_version.")
        statement = (
            update(RiskOverrideModel)
            .where(
                RiskOverrideModel.id == override.id.value,
                RiskOverrideModel.version == expected_version,
            )
            .values(**{key: value for key, value in values.items() if key != "id"})
        )
        result = cast(CursorResult[Any], self._session.execute(statement))
        if result.rowcount != 1:
            raise SafetyConcurrencyError("Stale RiskOverride version.")
        self._session.flush()

    @staticmethod
    def _values(override: RiskOverride) -> dict[str, object]:
        return {
            "id": override.id.value,
            "status": override.status.value,
            "account_id": override.scope.account_id,
            "strategy_id": override.scope.strategy_id,
            "risk_rule": override.scope.risk_rule,
            "instrument_id": override.scope.instrument_id,
            "reason": override.reason,
            "requested_by": override.requested_by.value,
            "approved_by": (
                override.approved_by.value
                if override.approved_by is not None
                else None
            ),
            "created_at": override.created_at,
            "valid_from": override.valid_from,
            "valid_until": override.valid_until,
            "approved_at": override.approved_at,
            "revoked_by": (
                override.revoked_by.value
                if override.revoked_by is not None
                else None
            ),
            "revoked_at": override.revoked_at,
            "correlation_id": override.correlation_id.value,
            "version": override.version,
        }

    @staticmethod
    def _from_model(row: RiskOverrideModel) -> RiskOverride:
        return RiskOverride(
            id=RiskOverrideId(row.id),
            scope=RiskOverrideScope(
                account_id=row.account_id,
                strategy_id=row.strategy_id,
                risk_rule=row.risk_rule,
                instrument_id=row.instrument_id,
            ),
            reason=row.reason,
            requested_by=ActorId(row.requested_by),
            created_at=row.created_at,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            correlation_id=CorrelationId(row.correlation_id),
            status=RiskOverrideStatus(row.status),
            approved_by=(
                ActorId(row.approved_by) if row.approved_by is not None else None
            ),
            approved_at=row.approved_at,
            revoked_by=(
                ActorId(row.revoked_by) if row.revoked_by is not None else None
            ),
            revoked_at=row.revoked_at,
            version=row.version,
        )


class PostgresDangerousActionConfirmationRepository:
    def __init__(
        self,
        session: Session,
        *,
        process_nonce: str,
    ) -> None:
        self._session = session
        self._process_nonce = process_nonce

    def get(
        self,
        confirmation_id: DangerousActionConfirmationId,
    ) -> DangerousActionConfirmation | None:
        row = self._session.get(
            DangerousActionConfirmationModel,
            confirmation_id.value,
        )
        if row is None or row.process_nonce != self._process_nonce:
            return None
        return DangerousActionConfirmation(
            id=DangerousActionConfirmationId(row.id),
            actor_id=ActorId(row.actor_id),
            action=DangerousAction(row.action),
            scope_reference=row.scope_reference,
            challenge_reference=row.challenge_reference,
            confirmed_at=row.confirmed_at,
            expires_at=row.expires_at,
            process_nonce=row.process_nonce,
            consumed_at=row.consumed_at,
        )

    def save(self, confirmation: DangerousActionConfirmation) -> None:
        row = self._session.get(
            DangerousActionConfirmationModel,
            confirmation.id.value,
        )
        values = {
            "id": confirmation.id.value,
            "actor_id": confirmation.actor_id.value,
            "action": confirmation.action.value,
            "scope_reference": confirmation.scope_reference,
            "challenge_reference": confirmation.challenge_reference,
            "confirmed_at": confirmation.confirmed_at,
            "expires_at": confirmation.expires_at,
            "process_nonce": confirmation.process_nonce,
            "consumed_at": confirmation.consumed_at,
        }
        if row is None:
            self._session.add(DangerousActionConfirmationModel(**values))
        else:
            for key, value in values.items():
                if key != "id":
                    setattr(row, key, value)
        self._session.flush()
