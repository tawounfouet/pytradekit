"""PostgreSQL RiskPolicyRepository implementation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pytradekit.risk.adapters.postgres.mapper import (
    risk_policy_from_model,
    risk_policy_to_values,
)
from pytradekit.risk.adapters.postgres.models import RiskPolicyModel
from pytradekit.risk.domain import RiskPolicy, RiskScope


class PostgresRiskPolicyRepository:
    """Durable repository preserving policy versions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, policy: RiskPolicy) -> None:
        row = self._session.get(RiskPolicyModel, policy.id.value)
        values = risk_policy_to_values(policy)
        if row is None:
            self._session.add(RiskPolicyModel(**values))
        else:
            for key, value in values.items():
                if key != "id":
                    setattr(row, key, value)
        self._session.flush()

    def get_active(self, scope: RiskScope, scope_id: str | None) -> RiskPolicy | None:
        statement = (
            select(RiskPolicyModel)
            .where(
                RiskPolicyModel.enabled.is_(True),
                RiskPolicyModel.scope == scope.value,
                RiskPolicyModel.scope_id == scope_id,
            )
            .order_by(RiskPolicyModel.policy_version.desc())
            .limit(1)
        )
        row = self._session.execute(statement).scalar_one_or_none()
        return risk_policy_from_model(row) if row is not None else None

    def list_active(self) -> tuple[RiskPolicy, ...]:
        statement = (
            select(RiskPolicyModel)
            .where(RiskPolicyModel.enabled.is_(True))
            .order_by(
                RiskPolicyModel.scope,
                RiskPolicyModel.scope_id,
                RiskPolicyModel.policy_version.desc(),
            )
        )
        rows = self._session.execute(statement).scalars().all()
        return tuple(risk_policy_from_model(row) for row in rows)
