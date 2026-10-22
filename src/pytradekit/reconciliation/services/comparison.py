"""Account snapshot comparison orchestration."""

from __future__ import annotations

from datetime import datetime

from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    InternalSnapshot,
    Mismatch,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
    ReconciliationScope,
    SnapshotCompleteness,
)

from ._support import mismatch, sort_mismatches
from .balance_comparator import BalanceComparator
from .fill_comparator import FillComparator
from .order_comparator import OrderComparator
from .position_comparator import PositionComparator


class SnapshotComparator:
    """Compose pure comparators for one requested reconciliation scope."""

    def __init__(
        self,
        *,
        orders: OrderComparator | None = None,
        fills: FillComparator | None = None,
        positions: PositionComparator | None = None,
        balances: BalanceComparator | None = None,
    ) -> None:
        self._orders = orders or OrderComparator()
        self._fills = fills or FillComparator()
        self._positions = positions or PositionComparator()
        self._balances = balances or BalanceComparator()

    def compare(
        self,
        *,
        run_id: ReconciliationRunId,
        scope: ReconciliationScope,
        internal: InternalSnapshot,
        broker: BrokerSnapshot,
        detected_at: datetime,
    ) -> tuple[Mismatch, ...]:
        """Return all P0 mismatches for the requested scope."""

        result: list[Mismatch] = []

        if internal.account_id != broker.account_id:
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=MismatchType.SNAPSHOT_UNAVAILABLE,
                    severity=MismatchSeverity.CRITICAL,
                    entity_type="account",
                    entity_id=str(internal.account_id),
                    internal_value={"account_id": str(internal.account_id)},
                    external_value={"account_id": str(broker.account_id)},
                    detected_at=detected_at,
                )
            )
            return sort_mismatches(result)

        result.extend(
            _completeness_mismatches(
                run_id=run_id,
                source="internal",
                completeness=internal.completeness,
                detected_at=detected_at,
            )
        )
        result.extend(
            _completeness_mismatches(
                run_id=run_id,
                source="broker",
                completeness=broker.completeness,
                detected_at=detected_at,
            )
        )

        if scope in {ReconciliationScope.ORDERS, ReconciliationScope.FULL}:
            result.extend(
                self._orders.compare(
                    run_id=run_id,
                    internal=internal.orders,
                    external=broker.orders,
                    detected_at=detected_at,
                )
            )

        if scope in {ReconciliationScope.FILLS, ReconciliationScope.FULL}:
            result.extend(
                self._fills.compare(
                    run_id=run_id,
                    internal=internal.fills,
                    external=broker.fills,
                    detected_at=detected_at,
                )
            )

        if scope in {ReconciliationScope.POSITIONS, ReconciliationScope.FULL}:
            result.extend(
                self._positions.compare(
                    run_id=run_id,
                    internal=internal.positions,
                    external=broker.positions,
                    detected_at=detected_at,
                )
            )

        if scope in {
            ReconciliationScope.ACCOUNT,
            ReconciliationScope.BALANCES,
            ReconciliationScope.FULL,
        }:
            result.extend(
                self._balances.compare(
                    run_id=run_id,
                    internal=internal.balances,
                    external=broker.balances,
                    detected_at=detected_at,
                )
            )

        return sort_mismatches(result)


def _completeness_mismatches(
    *,
    run_id: ReconciliationRunId,
    source: str,
    completeness: SnapshotCompleteness,
    detected_at: datetime,
) -> tuple[Mismatch, ...]:
    if completeness is SnapshotCompleteness.COMPLETE:
        return ()
    return (
        mismatch(
            run_id=run_id,
            mismatch_type=MismatchType.SNAPSHOT_INCOMPLETE,
            severity=(
                MismatchSeverity.CRITICAL
                if completeness is SnapshotCompleteness.UNKNOWN
                else MismatchSeverity.HIGH
            ),
            entity_type="snapshot",
            entity_id=source,
            internal_value=(
                {"completeness": completeness.value} if source == "internal" else None
            ),
            external_value=(
                {"completeness": completeness.value} if source == "broker" else None
            ),
            detected_at=detected_at,
        ),
    )
