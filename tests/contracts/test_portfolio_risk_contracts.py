"""Contract tests for Portfolio and Risk repository ports."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.portfolio.adapters import (
    InMemoryBalanceRepository,
    InMemoryPositionRepository,
)
from pytradekit.portfolio.domain import AccountId, Balance, Position
from pytradekit.portfolio.ports import BalanceRepository, PositionRepository
from pytradekit.risk.adapters import (
    InMemoryRiskPolicyRepository,
    InMemoryTradingHaltRepository,
)
from pytradekit.risk.domain import (
    RiskPolicy,
    RiskPolicyId,
    RiskScope,
    TradingHalt,
    TradingHaltId,
)
from pytradekit.risk.ports import RiskPolicyRepository, TradingHaltRepository
from pytradekit.shared import Currency, InstrumentId, Money, Price

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
USD = Currency("USD")


def _accept_position_repository(repository: PositionRepository) -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    position = Position.flat(
        account_id=account_id,
        instrument_id=instrument_id,
        currency=USD,
        occurred_at=NOW,
    )
    repository.save(position)

    loaded = repository.get(account_id, instrument_id)
    assert loaded == position
    assert repository.list_for_account(account_id) == (position,)


def _accept_balance_repository(repository: BalanceRepository) -> None:
    account_id = AccountId.new()
    balance = Balance(
        account_id=account_id,
        currency=USD,
        cash=Money(Decimal("1000"), USD),
        updated_at=NOW,
    )
    repository.save(balance)

    assert repository.get(account_id, USD) == balance
    assert repository.list_for_account(account_id) == (balance,)


def _accept_policy_repository(repository: RiskPolicyRepository) -> None:
    older = RiskPolicy(
        id=RiskPolicyId.new(),
        name="account-v1",
        scope=RiskScope.ACCOUNT,
        scope_id="account-1",
        limits=(),
        enabled=True,
        version=1,
    )
    newer = RiskPolicy(
        id=RiskPolicyId.new(),
        name="account-v2",
        scope=RiskScope.ACCOUNT,
        scope_id="account-1",
        limits=(),
        enabled=True,
        version=2,
    )
    repository.save(older)
    repository.save(newer)

    selected = repository.get_active(RiskScope.ACCOUNT, "account-1")
    assert selected is not None
    assert selected.version == 2


def _accept_halt_repository(repository: TradingHaltRepository) -> None:
    halt = TradingHalt(
        id=TradingHaltId.new(),
        scope=RiskScope.GLOBAL,
        scope_id=None,
        reason="qualification",
        triggered_at=NOW,
    )
    repository.save(halt)

    assert repository.get(halt.id) == halt
    assert repository.get_active(RiskScope.GLOBAL, None) == halt
    assert repository.list_active() == (halt,)


def test_in_memory_position_repository_contract() -> None:
    _accept_position_repository(InMemoryPositionRepository())


def test_in_memory_balance_repository_contract() -> None:
    _accept_balance_repository(InMemoryBalanceRepository())


def test_in_memory_risk_policy_repository_contract() -> None:
    _accept_policy_repository(InMemoryRiskPolicyRepository())


def test_in_memory_trading_halt_repository_contract() -> None:
    _accept_halt_repository(InMemoryTradingHaltRepository())


def test_position_contract_supports_non_flat_values() -> None:
    position = Position(
        account_id=AccountId.new(),
        instrument_id=InstrumentId.new(),
        quantity=Decimal("1"),
        average_price=Price(Decimal("100"), USD),
        realized_pnl=Money.zero(USD),
        opened_at=NOW,
        updated_at=NOW,
    )
    repository = InMemoryPositionRepository()
    repository.save(position)
    assert repository.get(position.account_id, position.instrument_id) == position
