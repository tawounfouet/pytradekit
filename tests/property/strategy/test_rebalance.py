from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.portfolio.domain import AccountId, PortfolioSnapshot
from pytradekit.reference import ContractSpecification
from pytradekit.shared import Currency, InstrumentId, Money, Price
from pytradekit.strategy import TargetPosition
from pytradekit.strategy.portfolio_construction import RebalanceService


@given(st.integers(min_value=-100, max_value=100))
def test_zero_current_position_rebalance_matches_integer_target(target_value: int) -> None:
    usd = Currency("USD")
    instrument_id = InstrumentId.new()
    snapshot = PortfolioSnapshot(
        account_id=AccountId.new(),
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        base_currency=usd,
        cash=(),
        positions=(),
        nav=Money(Decimal("10000"), usd),
        gross_exposure=Money.zero(usd),
        net_exposure=Money.zero(usd),
        realized_pnl=Money.zero(usd),
        unrealized_pnl=Money.zero(usd),
        leverage=Decimal("0"),
    )
    target = TargetPosition(
        instrument_id=instrument_id,
        target_quantity=Decimal(target_value),
    )
    intents = RebalanceService().build(
        target,
        portfolio=snapshot,
        reference_price=Price(Decimal("100"), usd),
        contract=ContractSpecification(quantity_step=Decimal("1")),
    )
    if target_value == 0:
        assert intents == ()
    else:
        assert intents[0].quantity.value == abs(Decimal(target_value))
