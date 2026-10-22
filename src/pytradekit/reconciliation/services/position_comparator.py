"""Deterministic canonical position comparison."""

from __future__ import annotations

from datetime import datetime

from pytradekit.reconciliation.domain import (
    CanonicalPosition,
    JsonEvidence,
    Mismatch,
    MismatchSeverity,
    MismatchType,
    ReconciliationRunId,
)

from ._support import mismatch, sort_mismatches


class PositionComparator:
    """Compare position quantities without provider mark-to-market noise."""

    def compare(
        self,
        *,
        run_id: ReconciliationRunId,
        internal: tuple[CanonicalPosition, ...],
        external: tuple[CanonicalPosition, ...],
        detected_at: datetime,
    ) -> tuple[Mismatch, ...]:
        """Return position quantity and presence mismatches."""

        local_by_id = {item.instrument_id: item for item in internal}
        remote_by_id = {item.instrument_id: item for item in external}
        result: list[Mismatch] = []

        for instrument_id in sorted(
            local_by_id.keys() - remote_by_id.keys(), key=str
        ):
            local = local_by_id[instrument_id]
            if local.quantity == 0:
                continue
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=MismatchType.POSITION_MISSING_EXTERNAL,
                    severity=MismatchSeverity.HIGH,
                    entity_type="position",
                    entity_id=str(instrument_id),
                    internal_value=_evidence(local),
                    external_value=None,
                    detected_at=detected_at,
                )
            )

        for instrument_id in sorted(
            remote_by_id.keys() - local_by_id.keys(), key=str
        ):
            remote = remote_by_id[instrument_id]
            if remote.quantity == 0:
                continue
            result.append(
                mismatch(
                    run_id=run_id,
                    mismatch_type=MismatchType.POSITION_MISSING_INTERNAL,
                    severity=MismatchSeverity.HIGH,
                    entity_type="position",
                    entity_id=str(instrument_id),
                    internal_value=None,
                    external_value=_evidence(remote),
                    detected_at=detected_at,
                )
            )

        for instrument_id in sorted(
            local_by_id.keys() & remote_by_id.keys(), key=str
        ):
            local = local_by_id[instrument_id]
            remote = remote_by_id[instrument_id]
            if local.quantity != remote.quantity:
                result.append(
                    mismatch(
                        run_id=run_id,
                        mismatch_type=MismatchType.POSITION_QUANTITY_MISMATCH,
                        severity=MismatchSeverity.HIGH,
                        entity_type="position",
                        entity_id=str(instrument_id),
                        internal_value=_evidence(local),
                        external_value=_evidence(remote),
                        detected_at=detected_at,
                    )
                )

        return sort_mismatches(result)


def _evidence(position: CanonicalPosition) -> JsonEvidence:
    return {
        "instrument_id": str(position.instrument_id),
        "quantity": str(position.quantity),
        "average_price": (
            str(position.average_price) if position.average_price is not None else ""
        ),
        "currency": str(position.currency) if position.currency is not None else "",
    }
