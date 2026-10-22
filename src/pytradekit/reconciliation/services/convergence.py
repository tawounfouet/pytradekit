"""Pure consistency and confidence computation."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    Mismatch,
    MismatchSeverity,
    SnapshotCompleteness,
    StateConfidence,
)


@dataclass(frozen=True, slots=True)
class ConvergenceResult:
    """Consistency decision derived only from reconciliation evidence."""

    status: ConsistencyStatus
    confidence: StateConfidence
    blocking: bool


class ConvergenceService:
    """Compute consistency independently from provider and persistence concerns."""

    def evaluate(
        self,
        *,
        internal_completeness: SnapshotCompleteness,
        broker_completeness: SnapshotCompleteness,
        mismatches: tuple[Mismatch, ...],
        unresolved_resolutions: int = 0,
    ) -> ConvergenceResult:
        """Return the safe convergence result for current evidence."""

        if unresolved_resolutions < 0:
            raise ValueError("unresolved_resolutions must be non-negative.")

        completeness = {internal_completeness, broker_completeness}
        severities = {item.severity for item in mismatches}

        if SnapshotCompleteness.UNKNOWN in completeness:
            return ConvergenceResult(
                status=ConsistencyStatus.UNKNOWN,
                confidence=StateConfidence.UNKNOWN,
                blocking=True,
            )

        if MismatchSeverity.CRITICAL in severities:
            return ConvergenceResult(
                status=ConsistencyStatus.INCONSISTENT,
                confidence=StateConfidence.LOW,
                blocking=True,
            )

        if MismatchSeverity.HIGH in severities:
            return ConvergenceResult(
                status=ConsistencyStatus.INCONSISTENT,
                confidence=StateConfidence.MEDIUM,
                blocking=True,
            )

        if SnapshotCompleteness.PARTIAL in completeness:
            return ConvergenceResult(
                status=ConsistencyStatus.DEGRADED,
                confidence=StateConfidence.MEDIUM,
                blocking=True,
            )

        if mismatches or unresolved_resolutions:
            return ConvergenceResult(
                status=ConsistencyStatus.DEGRADED,
                confidence=StateConfidence.MEDIUM,
                blocking=True,
            )

        return ConvergenceResult(
            status=ConsistencyStatus.CONSISTENT,
            confidence=StateConfidence.HIGH,
            blocking=False,
        )
