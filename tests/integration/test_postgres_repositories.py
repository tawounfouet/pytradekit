"""Repository contracts against real PostgreSQL."""

from decimal import Decimal

from sqlalchemy.orm import Session

from pytradekit.execution.adapters.postgres import PostgresFillRepository
from pytradekit.orders.adapters.postgres import PostgresOrderRepository
from pytradekit.portfolio.adapters.postgres import (
    PostgresBalanceRepository,
    PostgresPositionRepository,
    PostgresProcessedFillRegistry,
)
from pytradekit.risk.adapters.postgres import PostgresRiskPolicyRepository
from pytradekit.risk.domain import RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.risk.domain.rules import MaxLeverage, MaxOrderSize
from pytradekit.shared import Currency, Money
from tests.contracts.repository_contracts import (
    accept_balance_repository,
    accept_fill_repository,
    accept_order_repository,
    accept_position_repository,
    accept_processed_fill_registry,
)


def test_postgres_order_repository_contract(postgres_session: Session) -> None:
    accept_order_repository(PostgresOrderRepository(postgres_session))


def test_postgres_fill_repository_contract(postgres_session: Session) -> None:
    accept_fill_repository(PostgresFillRepository(postgres_session))


def test_postgres_position_repository_contract(postgres_session: Session) -> None:
    accept_position_repository(PostgresPositionRepository(postgres_session))


def test_postgres_balance_repository_contract(postgres_session: Session) -> None:
    accept_balance_repository(PostgresBalanceRepository(postgres_session))


def test_postgres_processed_fill_registry_contract(postgres_session: Session) -> None:
    accept_processed_fill_registry(PostgresProcessedFillRegistry(postgres_session))


def test_postgres_risk_policy_mapping_is_lossless(postgres_session: Session) -> None:
    usd = Currency("USD")
    policy = RiskPolicy(
        id=RiskPolicyId.new(),
        name="paper-account",
        scope=RiskScope.ACCOUNT,
        scope_id="account-1",
        limits=(
            MaxOrderSize(
                max_notional=Money(Decimal("5000"), usd),
                max_quantity=Decimal("10"),
            ),
            MaxLeverage(maximum=Decimal("2")),
        ),
        enabled=True,
        version=3,
    )
    repository = PostgresRiskPolicyRepository(postgres_session)
    repository.save(policy)

    assert repository.get_active(RiskScope.ACCOUNT, "account-1") == policy
