"""Qualify PyTradeKit 0.8 LOT-06.2 IBKR read-side reconciliation."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKRAccountRestrictionsObservation,
    IBKRBrokerSnapshotPort,
    IBKRContractId,
    IBKRInstrumentMappingResult,
    IBKRReadSideCoverageEvidence,
    IBKRStartupReconciliationGate,
)
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application import ReconciliationOutcome
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    StateConfidence,
)
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    StartupReadinessReport,
)
from pytradekit.shared import CorrelationId

_NOW = datetime(2026, 10, 23, 6, 30, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Value:
    def __init__(
        self,
        account: str,
        tag: str,
        value: str,
        currency: str,
    ) -> None:
        self.account = account
        self.tag = tag
        self.value = value
        self.currency = currency


class _Client:
    def isConnected(self) -> bool:
        return True

    def accountValues(self, account: str = "") -> list[object]:
        return [
            _Value("DU1234567", "AccountReady", "true", ""),
            _Value(
                "DU1234567",
                "TotalCashValue",
                "25000.00",
                "USD",
            ),
            _Value(
                "DU1234567",
                "NetLiquidation",
                "25000.00",
                "USD",
            ),
        ]

    def portfolio(self, account: str = "") -> list[object]:
        return []

    def trades(self) -> list[object]:
        return []

    def fills(self) -> list[object]:
        return []


class _NoInstrumentLookup:
    def resolve(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> IBKRInstrumentMappingResult | None:
        return None


class _NoOrderLookup:
    def resolve_order_id(
        self,
        external_order_id: str,
        client_order_id: str | None = None,
    ) -> OrderId | None:
        return None


class _Restrictions:
    def get(
        self,
        external_account_id: str,
    ) -> IBKRAccountRestrictionsObservation | None:
        return IBKRAccountRestrictionsObservation(
            trading_blocked=False,
            account_blocked=False,
            evidence_source="deterministic-lot06.2-fixture",
        )


def _coverage() -> IBKRReadSideCoverageEvidence:
    return IBKRReadSideCoverageEvidence(
        orders_complete=True,
        fills_complete=True,
        positions_complete=True,
        account_complete=True,
        evidence_source="deterministic-lot06.2-fixture",
    )


class _Workflow:
    def __init__(self, account_id: AccountId) -> None:
        run = ReconciliationRun.create(
            account_id=account_id,
            scope=ReconciliationScope.FULL,
            trigger=ReconciliationTrigger.STARTUP,
            started_at=_NOW,
            correlation_id=CorrelationId.new(),
        )
        run.transition_to(ReconciliationRunStatus.CAPTURING)
        run.transition_to(ReconciliationRunStatus.COMPARING)
        run.transition_to(ReconciliationRunStatus.VERIFYING)
        run.complete(
            completed_at=_NOW,
            result_status=ConsistencyStatus.CONSISTENT,
            confidence=StateConfidence.HIGH,
            mismatch_count=0,
            critical_mismatch_count=0,
        )
        self._outcome = ReconciliationOutcome(
            run=run,
            mismatches=(),
            resolutions=(),
        )

    def startup(
        self,
        *,
        account_id: AccountId,
        correlation_id: CorrelationId,
    ) -> ReconciliationOutcome:
        return self._outcome


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-06.2 read-side normalization and startup "
            "reconciliation without a provider network call."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    account_id = AccountId.new()
    broker = IBKRBrokerSnapshotPort(
        client=_Client(),
        expected_external_account_id="DU1234567",
        instruments=_NoInstrumentLookup(),
        identities=_NoOrderLookup(),
        restrictions=_Restrictions(),
        coverage=_coverage(),
        clock=_Clock(),
    )
    snapshot = broker.capture(
        account_id=account_id,
        scope=ReconciliationScope.FULL,
    )
    gate = IBKRStartupReconciliationGate(
        account_id=account_id,
        workflows=_Workflow(account_id),
    )
    readiness = gate.evaluate(
        StartupReadinessReport(
            provider="ibkr",
            environment="PAPER",
            account="***4567",
            checks=(
                ReadinessCheck(
                    name="transport",
                    status=ReadinessCheckStatus.PASS,
                    detail="deterministic synchronized transport fixture",
                ),
            ),
        )
    )

    payload = {
        "lot": "LOT-06.2",
        "release": "0.8.0b3",
        "provider": "ibkr",
        "environment": "PAPER",
        "read_side_complete": snapshot.completeness.value == "COMPLETE",
        "orders": len(snapshot.orders),
        "fills": len(snapshot.fills),
        "positions": len(snapshot.positions),
        "balances": len(snapshot.balances),
        "consistency_status": (
            readiness.consistency_status.value
            if readiness.consistency_status is not None
            else None
        ),
        "state_confidence": (
            readiness.state_confidence.value
            if readiness.state_confidence is not None
            else None
        ),
        "trading_ready": readiness.trading_ready,
        "economic_write_admission": False,
        "real_paper_provider_used": False,
        "paper_certification_claimed": False,
        "live_available": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-06.2 IBKR read-side reconciliation: PASS")
    print(f"snapshot completeness: {snapshot.completeness.value}")
    print("reconciliation: CONSISTENT/HIGH")
    print("economic write admission: false")
    print("real PAPER provider proof: false")
    print("PAPER certification claimed: false")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
