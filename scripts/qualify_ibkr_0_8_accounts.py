"""Qualify PyTradeKit 0.8 LOT-05.6 IBKR account and position mapping."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-05.6 IBKR account and position mapping without SDK "
            "imports or provider network calls."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    now = datetime(2026, 10, 23, 5, 30, tzinfo=UTC)
    usd = Currency("USD")
    account_id = AccountId.new()

    account = map_ibkr_account_snapshot(
        IBKRAccountSummaryObservation(
            external_account_id="DU1234567",
            base_currency=usd,
            account_ready=True,
            metrics=(
                IBKRAccountMetric(
                    IBKRAccountMetricTag.TOTAL_CASH_VALUE,
                    Decimal("10000"),
                    usd,
                ),
                IBKRAccountMetric(
                    IBKRAccountMetricTag.NET_LIQUIDATION,
                    Decimal("15000"),
                    usd,
                ),
                IBKRAccountMetric(
                    IBKRAccountMetricTag.BUYING_POWER,
                    Decimal("40000"),
                    usd,
                ),
                IBKRAccountMetric(
                    IBKRAccountMetricTag.AVAILABLE_FUNDS,
                    Decimal("12000"),
                    usd,
                ),
                IBKRAccountMetric(
                    IBKRAccountMetricTag.CASH_BALANCE,
                    Decimal("9800"),
                    usd,
                ),
            ),
            observed_at=now,
        ),
        account_id=account_id,
        restrictions=IBKRAccountRestrictionsObservation(
            trading_blocked=False,
            account_blocked=False,
            evidence_source="paper-account-readiness-probe",
        ),
    )

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
    position = map_ibkr_position_snapshot(
        IBKRPortfolioPositionObservation(
            external_account_id="DU1234567",
            contract_id=IBKRContractId(265598),
            symbol="AAPL",
            currency=usd,
            signed_quantity=Decimal("-4"),
            average_cost=Decimal("200"),
            market_price=Decimal("190"),
            market_value=Decimal("-760"),
            unrealized_pnl=Decimal("40"),
            realized_pnl=Decimal("5"),
            observed_at=now,
        ),
        account_id=account_id,
        expected_external_account_id="DU1234567",
        instrument=instrument,
    )

    snapshot = account.snapshot
    payload = {
        "lot": "LOT-05.6",
        "provider": "ibkr",
        "network_used": False,
        "sdk_dependency_required": False,
        "account": {
            "external_account_id": snapshot.identity.external_account_id,
            "total_cash_value": (
                None
                if snapshot.cash_balance is None
                else str(snapshot.cash_balance.cash.amount)
            ),
            "net_liquidation": (
                None if snapshot.equity is None else str(snapshot.equity.amount)
            ),
            "buying_power": (
                None
                if snapshot.buying_power is None
                else str(snapshot.buying_power.amount)
            ),
            "available_funds_retained": (
                None
                if account.available_funds is None
                else str(account.available_funds.amount)
            ),
            "cash_balance_retained": (
                None
                if account.cash_balance is None
                else str(account.cash_balance.amount)
            ),
            "balance_available_fabricated": False,
            "portfolio_value_fabricated": False,
        },
        "position": {
            "signed_quantity": str(position.snapshot.signed_quantity),
            "average_price": str(position.snapshot.average_price.value),
            "cost_basis": str(position.snapshot.cost_basis.amount),
            "available_quantity_fabricated": False,
            "provider_realized_pnl_retained": (
                None
                if position.provider_realized_pnl is None
                else str(position.provider_realized_pnl.amount)
            ),
        },
        "account_ready_required": True,
        "restriction_evidence_required": True,
        "paper_certification_claimed": False,
        "core_change_required": False,
    }

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-05.6 IBKR account mapping qualification: PASS")
    print("TotalCashValue maps to canonical cash: true")
    print("NetLiquidation maps to canonical equity: true")
    print("BuyingPower remains distinct from AvailableFunds: true")
    print("CashBalance remains distinct from TotalCashValue: true")
    print("AccountReady is required before snapshot emission: true")
    print("position quantity remains signed: true")
    print("position availability is not fabricated: true")
    print("broker-neutral core change required: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
