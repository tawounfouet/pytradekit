"""LOT-05.6 qualification for IBKR account, balance, and position mapping."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.brokers.adapters.ibkr import (
    IBKRAccountMetric,
    IBKRAccountMetricTag,
    IBKRAccountRestrictionsObservation,
    IBKRAccountSummaryObservation,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRPortfolioPositionObservation,
    IBKRSecurityType,
    map_ibkr_account_snapshot,
    map_ibkr_position_snapshot,
    map_ibkr_stock_contract,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import Currency, InstrumentId

_NOW = datetime(2026, 10, 23, 5, 30, tzinfo=UTC)
_USD = Currency("USD")


def test_lot05_6_preserves_distinct_account_semantics() -> None:
    account_id = AccountId.new()
    observation = IBKRAccountSummaryObservation(
        external_account_id="DU1234567",
        base_currency=_USD,
        account_ready=True,
        metrics=(
            IBKRAccountMetric(
                IBKRAccountMetricTag.TOTAL_CASH_VALUE,
                Decimal("10000"),
                _USD,
            ),
            IBKRAccountMetric(
                IBKRAccountMetricTag.NET_LIQUIDATION,
                Decimal("15000"),
                _USD,
            ),
            IBKRAccountMetric(
                IBKRAccountMetricTag.BUYING_POWER,
                Decimal("40000"),
                _USD,
            ),
            IBKRAccountMetric(
                IBKRAccountMetricTag.AVAILABLE_FUNDS,
                Decimal("12000"),
                _USD,
            ),
            IBKRAccountMetric(
                IBKRAccountMetricTag.CASH_BALANCE,
                Decimal("9800"),
                _USD,
            ),
        ),
        observed_at=_NOW,
    )

    result = map_ibkr_account_snapshot(
        observation,
        account_id=account_id,
        restrictions=IBKRAccountRestrictionsObservation(
            trading_blocked=False,
            account_blocked=False,
            evidence_source="paper-account-readiness-probe",
        ),
    )

    assert result.snapshot.cash_balance is not None
    assert result.snapshot.cash_balance.cash.amount == Decimal("10000")
    assert result.snapshot.cash_balance.available is None
    assert result.snapshot.equity is not None
    assert result.snapshot.equity.amount == Decimal("15000")
    assert result.snapshot.buying_power is not None
    assert result.snapshot.buying_power.amount == Decimal("40000")
    assert result.available_funds is not None
    assert result.available_funds.amount == Decimal("12000")
    assert result.cash_balance is not None
    assert result.cash_balance.amount == Decimal("9800")
    assert result.snapshot.portfolio_value is None


def test_lot05_6_maps_signed_position_without_fabricated_availability() -> None:
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    instrument = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=InstrumentId.new(),
    )

    result = map_ibkr_position_snapshot(
        IBKRPortfolioPositionObservation(
            external_account_id="DU1234567",
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
            currency=_USD,
            signed_quantity=Decimal("-4"),
            average_cost=Decimal("200"),
            market_price=Decimal("190"),
            market_value=Decimal("-760"),
            unrealized_pnl=Decimal("40"),
            realized_pnl=Decimal("5"),
            observed_at=_NOW,
        ),
        account_id=AccountId.new(),
        expected_external_account_id="DU1234567",
        instrument=instrument,
    )

    assert result.snapshot.signed_quantity == Decimal("-4")
    assert result.snapshot.cost_basis.amount == Decimal("800")
    assert result.snapshot.available_quantity is None
    assert result.provider_realized_pnl is not None
    assert result.provider_realized_pnl.amount == Decimal("5")
