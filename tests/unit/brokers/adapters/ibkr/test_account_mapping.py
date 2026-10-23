"""Unit tests for IBKR account, balance, and position mapping."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import ProviderProtocolError
from pytradekit.brokers.adapters.ibkr import (
    IBKRAccountMappingError,
    IBKRAccountMetric,
    IBKRAccountMetricTag,
    IBKRAccountRestrictionsObservation,
    IBKRAccountSummaryObservation,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRInstrumentMappingResult,
    IBKRPortfolioPositionObservation,
    IBKRSecurityType,
    map_ibkr_account_snapshot,
    map_ibkr_position_snapshot,
    map_ibkr_stock_contract,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import Currency, InstrumentId

_NOW = datetime(2026, 10, 23, 5, 15, tzinfo=UTC)
_USD = Currency("USD")


def _metric(
    tag: IBKRAccountMetricTag,
    value: str,
    currency: Currency = _USD,
) -> IBKRAccountMetric:
    return IBKRAccountMetric(
        tag=tag,
        value=Decimal(value),
        currency=currency,
    )


def _account_observation(
    *,
    ready: bool = True,
) -> IBKRAccountSummaryObservation:
    return IBKRAccountSummaryObservation(
        external_account_id="DU1234567",
        base_currency=_USD,
        account_ready=ready,
        metrics=(
            _metric(IBKRAccountMetricTag.TOTAL_CASH_VALUE, "10000.00"),
            _metric(IBKRAccountMetricTag.NET_LIQUIDATION, "15000.00"),
            _metric(IBKRAccountMetricTag.BUYING_POWER, "40000.00"),
            _metric(IBKRAccountMetricTag.AVAILABLE_FUNDS, "12000.00"),
            _metric(IBKRAccountMetricTag.EQUITY_WITH_LOAN_VALUE, "14900.00"),
            _metric(IBKRAccountMetricTag.CASH_BALANCE, "9800.00"),
            _metric(IBKRAccountMetricTag.EXCESS_LIQUIDITY, "11500.00"),
            _metric(IBKRAccountMetricTag.INIT_MARGIN_REQ, "3000.00"),
            _metric(IBKRAccountMetricTag.MAINT_MARGIN_REQ, "2500.00"),
        ),
        observed_at=_NOW,
    )


def _restrictions() -> IBKRAccountRestrictionsObservation:
    return IBKRAccountRestrictionsObservation(
        trading_blocked=False,
        account_blocked=False,
        evidence_source="paper-account-readiness-probe",
    )


def _instrument() -> IBKRInstrumentMappingResult:
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    mapping = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=InstrumentId.new(),
    )
    return mapping


def test_account_mapping_keeps_cash_equity_and_margin_semantics_distinct() -> None:
    account_id = AccountId.new()

    result = map_ibkr_account_snapshot(
        _account_observation(),
        account_id=account_id,
        restrictions=_restrictions(),
    )

    snapshot = result.snapshot
    assert snapshot.identity.provider == "ibkr"
    assert snapshot.identity.external_account_id == "DU1234567"
    assert snapshot.account.id == account_id
    assert snapshot.account.base_currency == _USD

    assert snapshot.cash_balance is not None
    assert snapshot.cash_balance.cash.amount == Decimal("10000.00")
    assert snapshot.cash_balance.available is None
    assert snapshot.cash_balance.reserved is None

    assert snapshot.equity is not None
    assert snapshot.equity.amount == Decimal("15000.00")
    assert snapshot.buying_power is not None
    assert snapshot.buying_power.amount == Decimal("40000.00")
    assert snapshot.portfolio_value is None

    assert result.available_funds is not None
    assert result.available_funds.amount == Decimal("12000.00")
    assert result.cash_balance is not None
    assert result.cash_balance.amount == Decimal("9800.00")
    assert result.equity_with_loan_value is not None
    assert result.equity_with_loan_value.amount == Decimal("14900.00")


def test_available_funds_does_not_become_balance_available() -> None:
    result = map_ibkr_account_snapshot(
        _account_observation(),
        account_id=AccountId.new(),
        restrictions=_restrictions(),
    )

    assert result.snapshot.cash_balance is not None
    assert result.snapshot.cash_balance.available is None
    assert result.available_funds is not None


def test_cash_balance_does_not_replace_total_cash_value() -> None:
    result = map_ibkr_account_snapshot(
        _account_observation(),
        account_id=AccountId.new(),
        restrictions=_restrictions(),
    )

    assert result.snapshot.cash_balance is not None
    assert result.snapshot.cash_balance.cash.amount == Decimal("10000.00")
    assert result.cash_balance is not None
    assert result.cash_balance.amount == Decimal("9800.00")


def test_account_not_ready_fails_closed() -> None:
    with pytest.raises(ProviderProtocolError, match="not ready"):
        map_ibkr_account_snapshot(
            _account_observation(ready=False),
            account_id=AccountId.new(),
            restrictions=_restrictions(),
        )


def test_restriction_evidence_is_required_instead_of_fabricating_flags() -> None:
    with pytest.raises(IBKRAccountMappingError, match="restrictions"):
        map_ibkr_account_snapshot(
            _account_observation(),
            account_id=AccountId.new(),
            restrictions=None,  # type: ignore[arg-type]
        )


def test_multi_currency_metric_is_retained_but_not_used_as_base_cash() -> None:
    eur = Currency("EUR")
    observation = IBKRAccountSummaryObservation(
        external_account_id="DU1234567",
        base_currency=_USD,
        account_ready=True,
        metrics=(
            _metric(IBKRAccountMetricTag.TOTAL_CASH_VALUE, "10000.00"),
            _metric(IBKRAccountMetricTag.CASH_BALANCE, "2000.00", eur),
        ),
        observed_at=_NOW,
    )

    result = map_ibkr_account_snapshot(
        observation,
        account_id=AccountId.new(),
        restrictions=_restrictions(),
    )

    assert result.snapshot.cash_balance is not None
    assert result.snapshot.cash_balance.cash.amount == Decimal("10000.00")
    assert result.cash_balance is None
    eur_cash = observation.metric(
        IBKRAccountMetricTag.CASH_BALANCE,
        currency=eur,
    )
    assert eur_cash is not None
    assert eur_cash.value == Decimal("2000.00")


def test_duplicate_metric_tag_currency_pair_is_rejected() -> None:
    with pytest.raises(IBKRAccountMappingError, match="unique"):
        IBKRAccountSummaryObservation(
            external_account_id="DU1234567",
            base_currency=_USD,
            account_ready=True,
            metrics=(
                _metric(IBKRAccountMetricTag.NET_LIQUIDATION, "100"),
                _metric(IBKRAccountMetricTag.NET_LIQUIDATION, "101"),
            ),
            observed_at=_NOW,
        )


def test_long_position_maps_to_provider_neutral_snapshot() -> None:
    instrument = _instrument()
    account_id = AccountId.new()
    observation = IBKRPortfolioPositionObservation(
        external_account_id="DU1234567",
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        currency=_USD,
        signed_quantity=Decimal("10"),
        average_cost=Decimal("200.00"),
        market_price=Decimal("210.00"),
        market_value=Decimal("2100.00"),
        unrealized_pnl=Decimal("100.00"),
        realized_pnl=Decimal("25.00"),
        observed_at=_NOW,
    )

    result = map_ibkr_position_snapshot(
        observation,
        account_id=account_id,
        expected_external_account_id="DU1234567",
        instrument=instrument,
    )

    snapshot = result.snapshot
    assert snapshot.account_id == account_id
    assert snapshot.instrument_id == instrument.instrument.id
    assert snapshot.provider_instrument.external_id == "265598"
    assert snapshot.signed_quantity == Decimal("10")
    assert snapshot.average_price.value == Decimal("200.00")
    assert snapshot.cost_basis.amount == Decimal("2000.00")
    assert snapshot.market_value is not None
    assert snapshot.market_value.amount == Decimal("2100.00")
    assert snapshot.unrealized_pnl is not None
    assert snapshot.unrealized_pnl.amount == Decimal("100.00")
    assert snapshot.current_price is not None
    assert snapshot.current_price.value == Decimal("210.00")
    assert snapshot.available_quantity is None
    assert result.provider_realized_pnl is not None
    assert result.provider_realized_pnl.amount == Decimal("25.00")


def test_short_position_keeps_signed_quantity_and_cost_basis_magnitude() -> None:
    instrument = _instrument()
    observation = IBKRPortfolioPositionObservation(
        external_account_id="DU1234567",
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        currency=_USD,
        signed_quantity=Decimal("-4"),
        average_cost=Decimal("200.00"),
        market_price=Decimal("190.00"),
        market_value=Decimal("-760.00"),
        unrealized_pnl=Decimal("40.00"),
        realized_pnl=None,
        observed_at=_NOW,
    )

    result = map_ibkr_position_snapshot(
        observation,
        account_id=AccountId.new(),
        expected_external_account_id="DU1234567",
        instrument=instrument,
    )

    assert result.snapshot.signed_quantity == Decimal("-4")
    assert result.snapshot.cost_basis.amount == Decimal("800.00")
    assert result.snapshot.market_value is not None
    assert result.snapshot.market_value.amount == Decimal("-760.00")


def test_position_without_portfolio_marks_keeps_optional_values_unknown() -> None:
    instrument = _instrument()
    observation = IBKRPortfolioPositionObservation(
        external_account_id="DU1234567",
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        currency=_USD,
        signed_quantity=Decimal("3"),
        average_cost=Decimal("200.00"),
        market_price=None,
        market_value=None,
        unrealized_pnl=None,
        realized_pnl=None,
        observed_at=_NOW,
    )

    result = map_ibkr_position_snapshot(
        observation,
        account_id=AccountId.new(),
        expected_external_account_id="DU1234567",
        instrument=instrument,
    )

    assert result.snapshot.market_value is None
    assert result.snapshot.unrealized_pnl is None
    assert result.snapshot.current_price is None
    assert result.provider_realized_pnl is None


def _position_observation(
    *,
    external_account_id: str = "DU1234567",
    contract_id: IBKRContractId | None = None,
    symbol: str = "AAPL",
    currency: Currency = _USD,
) -> IBKRPortfolioPositionObservation:
    return IBKRPortfolioPositionObservation(
        external_account_id=external_account_id,
        contract_id=contract_id or IBKRContractId(265598),
        symbol=symbol,
        currency=currency,
        signed_quantity=Decimal("1"),
        average_cost=Decimal("200"),
        market_price=None,
        market_value=None,
        unrealized_pnl=None,
        realized_pnl=None,
        observed_at=_NOW,
    )


def test_position_account_mismatch_is_protocol_error() -> None:
    with pytest.raises(ProviderProtocolError, match="account"):
        map_ibkr_position_snapshot(
            _position_observation(external_account_id="OTHER"),
            account_id=AccountId.new(),
            expected_external_account_id="DU1234567",
            instrument=_instrument(),
        )


def test_position_contract_mismatch_is_protocol_error() -> None:
    with pytest.raises(ProviderProtocolError, match="conId"):
        map_ibkr_position_snapshot(
            _position_observation(contract_id=IBKRContractId(999999)),
            account_id=AccountId.new(),
            expected_external_account_id="DU1234567",
            instrument=_instrument(),
        )


def test_position_symbol_mismatch_is_protocol_error() -> None:
    with pytest.raises(ProviderProtocolError, match="symbol"):
        map_ibkr_position_snapshot(
            _position_observation(symbol="MSFT"),
            account_id=AccountId.new(),
            expected_external_account_id="DU1234567",
            instrument=_instrument(),
        )


def test_position_currency_mismatch_is_protocol_error() -> None:
    with pytest.raises(ProviderProtocolError, match="currency"):
        map_ibkr_position_snapshot(
            _position_observation(currency=Currency("EUR")),
            account_id=AccountId.new(),
            expected_external_account_id="DU1234567",
            instrument=_instrument(),
        )

def test_flat_position_is_not_fabricated_into_open_position_snapshot() -> None:
    with pytest.raises(IBKRAccountMappingError, match="non-zero"):
        IBKRPortfolioPositionObservation(
            external_account_id="DU1234567",
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
            currency=_USD,
            signed_quantity=Decimal("0"),
            average_cost=Decimal("200"),
            market_price=None,
            market_value=None,
            unrealized_pnl=None,
            realized_pnl=None,
            observed_at=_NOW,
        )
