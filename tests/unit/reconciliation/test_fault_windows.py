"""Reconciliation fault windows and critical position safety."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.reconciliation import (
    CanonicalPosition,
    MismatchSeverity,
    ReconciliationRunId,
)
from pytradekit.reconciliation.services import PositionComparator
from pytradekit.runtime.faults import FaultPoint, OneShotFaultInjector
from pytradekit.shared import InstrumentId

NOW = datetime(2026, 10, 22, 18, tzinfo=UTC)


def test_reconciliation_fault_points_are_available_to_qualification() -> None:
    required = {
        FaultPoint.BEFORE_RECONCILIATION_CAPTURE,
        FaultPoint.AFTER_RECONCILIATION_COMPARE,
        FaultPoint.BEFORE_RECONCILIATION_RESOLUTION,
        FaultPoint.AFTER_RECONCILIATION_RESOLUTION,
        FaultPoint.BEFORE_RECONCILIATION_VERIFY,
        FaultPoint.AFTER_RECONCILIATION_COMPLETE,
    }

    injector = OneShotFaultInjector(FaultPoint.AFTER_RECONCILIATION_COMPARE)

    assert required.issubset(set(FaultPoint))
    assert injector is not None


def test_position_quantity_divergence_is_critical() -> None:
    instrument_id = InstrumentId.new()
    local = CanonicalPosition(
        instrument_id=instrument_id,
        quantity=Decimal("1"),
        average_price=None,
        currency=None,
    )
    remote = CanonicalPosition(
        instrument_id=instrument_id,
        quantity=Decimal("2"),
        average_price=None,
        currency=None,
    )

    mismatches = PositionComparator().compare(
        run_id=ReconciliationRunId.new(),
        internal=(local,),
        external=(remote,),
        detected_at=NOW,
    )

    assert len(mismatches) == 1
    assert mismatches[0].severity is MismatchSeverity.CRITICAL
