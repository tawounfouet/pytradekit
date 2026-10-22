"""Deterministic canonical cash balance comparison."""

from __future__ import annotations

from datetime import datetime

from pytradekit.reconciliation.domain import (
    CanonicalBalance,
    Mismatch,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
)

from ._support import mismatch, sort_mismatches


class BalanceComparator:
    """Compare canonical cash by currency with exact Decimal semantics."""

    def compare(
        self,
        *,
        run_id: ReconciliationRunId,
        internal: tuple[CanonicalBalance, ...],
        external: tuple[CanonicalBalance, ...],
        detected_at: datetime,
    ) -> tuple[Mismatch, ...]:
        """Return deterministic cash mismatches."""

        local = {str(item.currency): item for item in internal}
        remote = {str(item.currency): item for item in external}
        result: list[Mismatch] = []

        for currency in sorted(local.keys() | remote.keys()):
            left = local.get(currency)
            right = remote.get(currency)
            if left is not None and right is not None and left.cash == right.cash:
                continue
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=MismatchType.BALANCE_MISMATCH,
                    severity=MismatchSeverity.HIGH,
                    entity_type="balance",
                    entity_id=currency,
                    internal_value=_evidence(left),
                    external_value=_evidence(right),
                    detected_at=detected_at,
                )
            )

        return sort_mismatches(result)


def _evidence(balance: CanonicalBalance | None) -> dict[str, str] | None:
    if balance is None:
        return None
    return {
        "currency": str(balance.currency),
        "cash": str(balance.cash),
    }
