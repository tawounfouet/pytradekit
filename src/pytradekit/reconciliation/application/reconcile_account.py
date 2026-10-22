"""Generic account reconciliation orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.application.resolve_mismatch import ResolveMismatch
from pytradekit.reconciliation.application.verify_reconciliation import VerifyReconciliation
from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    JsonEvidence,
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    Resolution,
    ResolutionStatus,
    SnapshotWatermark,
)
from pytradekit.reconciliation.ports import (
    BrokerSnapshotPort,
    ConsistencyEvidenceSinkPort,
    InternalSnapshotPort,
    ReconciliationRepository,
    RecoveryNotifierPort,
    ResolutionExecutorPort,
)
from pytradekit.reconciliation.services import ConvergenceService, SnapshotComparator
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import CorrelationId


class ReconciliationAlreadyRunningError(RuntimeError):
    """Raised when an account already has an active reconciliation run."""


class StaleReconciliationError(RuntimeError):
    """Raised before a correction can use superseded internal evidence."""


@dataclass(frozen=True, slots=True)
class ReconciliationOutcome:
    """Final auditable result of one reconciliation run."""

    run: ReconciliationRun
    mismatches: tuple[Mismatch, ...]
    resolutions: tuple[Resolution, ...]


class ReconcileAccount:
    """Run capture, comparison, resolution, fresh verification, and convergence."""

    def __init__(
        self,
        *,
        repository: ReconciliationRepository,
        internal_snapshots: InternalSnapshotPort,
        broker_snapshots: BrokerSnapshotPort,
        clock: ClockPort,
        comparator: SnapshotComparator | None = None,
        convergence: ConvergenceService | None = None,
        resolver: ResolveMismatch | None = None,
        executor: ResolutionExecutorPort | None = None,
        notifier: RecoveryNotifierPort | None = None,
        evidence_sink: ConsistencyEvidenceSinkPort | None = None,
    ) -> None:
        self._repository = repository
        self._internal_snapshots = internal_snapshots
        self._broker_snapshots = broker_snapshots
        self._clock = clock
        self._comparator = comparator or SnapshotComparator()
        self._convergence = convergence or ConvergenceService()
        self._resolver = resolver or ResolveMismatch(clock=clock)
        self._executor = executor
        self._notifier = notifier
        self._evidence_sink = evidence_sink
        self._verifier = VerifyReconciliation(
            internal_snapshots=internal_snapshots,
            broker_snapshots=broker_snapshots,
            comparator=self._comparator,
            clock=clock,
        )

    def execute(
        self,
        *,
        account_id: AccountId,
        trigger: ReconciliationTrigger,
        correlation_id: CorrelationId,
        scope: ReconciliationScope = ReconciliationScope.FULL,
    ) -> ReconciliationOutcome:
        self._ensure_account_available(account_id)
        run = ReconciliationRun.create(
            account_id=account_id,
            scope=scope,
            trigger=trigger,
            started_at=self._clock.now(),
            correlation_id=correlation_id,
        )
        self._repository.add_run(run)
        self._repository.checkpoint()
        try:
            run.transition_to(ReconciliationRunStatus.CAPTURING)
            self._repository.save_run(run)
            self._repository.checkpoint()
            internal = self._internal_snapshots.capture(
                account_id=account_id,
                scope=scope,
            )
            broker = self._broker_snapshots.capture(
                account_id=account_id,
                scope=scope,
            )
            run.internal_watermark = internal.watermark
            run.broker_watermark = broker.watermark
            run.transition_to(ReconciliationRunStatus.COMPARING)
            self._repository.save_run(run)
            self._repository.checkpoint()

            initial = self._comparator.compare(
                run_id=run.id,
                scope=scope,
                internal=internal,
                broker=broker,
                detected_at=self._clock.now(),
            )
            for item in initial:
                self._repository.add_mismatch(item)
            if initial:
                self._repository.checkpoint()

            critical_count = sum(
                item.severity is MismatchSeverity.CRITICAL for item in initial
            )
            if critical_count and self._notifier is not None:
                self._notifier.critical_mismatch(run, count=critical_count)

            resolutions = tuple(
                self._resolver.plan(item, correlation_id=correlation_id)
                for item in initial
            )
            for resolution in resolutions:
                self._repository.add_resolution(resolution)
            if resolutions:
                self._repository.checkpoint()

            if resolutions:
                run.transition_to(ReconciliationRunStatus.RESOLVING)
                self._repository.save_run(run)
            self._repository.checkpoint()
                self._apply_supported(
                    resolutions,
                    initial,
                    broker,
                    account_id=account_id,
                    scope=scope,
                    original_watermark=internal.watermark,
                    run=run,
                )

            run.transition_to(ReconciliationRunStatus.VERIFYING)
            self._repository.save_run(run)
            self._repository.checkpoint()
            verification = self._verifier.execute(
                run_id=run.id,
                account_id=account_id,
                scope=scope,
            )
            self._verify_applied(resolutions, initial, verification.mismatches)

            unresolved = sum(
                item.status is not ResolutionStatus.VERIFIED for item in resolutions
            )
            result = self._convergence.evaluate(
                internal_completeness=verification.internal.completeness,
                broker_completeness=verification.broker.completeness,
                mismatches=verification.mismatches,
                unresolved_resolutions=unresolved,
            )
            final_critical = sum(
                item.severity is MismatchSeverity.CRITICAL
                for item in verification.mismatches
            )
            run.internal_watermark = verification.internal.watermark
            run.broker_watermark = verification.broker.watermark
            run.complete(
                completed_at=self._clock.now(),
                result_status=result.status,
                confidence=result.confidence,
                mismatch_count=len(verification.mismatches),
                critical_mismatch_count=final_critical,
            )
            self._repository.save_run(run)
            self._repository.checkpoint()
            if self._evidence_sink is not None:
                self._evidence_sink.record(run)
            if self._notifier is not None and not result.blocking:
                self._notifier.recovery_verified(run)
            return ReconciliationOutcome(
                run=run,
                mismatches=verification.mismatches,
                resolutions=resolutions,
            )
        except Exception as exc:
            if run.status not in {
                ReconciliationRunStatus.COMPLETED,
                ReconciliationRunStatus.FAILED,
                ReconciliationRunStatus.CANCELLED,
            }:
                run.fail(completed_at=self._clock.now())
                self._repository.save_run(run)
            self._repository.checkpoint()
            if self._notifier is not None:
                self._notifier.recovery_failed(run, reason=type(exc).__name__)
            raise

    def _ensure_account_available(self, account_id: AccountId) -> None:
        if any(run.account_id == account_id for run in self._repository.list_active()):
            raise ReconciliationAlreadyRunningError(
                f"Account {account_id} already has an active reconciliation run."
            )

    def _apply_supported(
        self,
        resolutions: tuple[Resolution, ...],
        mismatches: tuple[Mismatch, ...],
        broker_snapshot: BrokerSnapshot,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
        original_watermark: SnapshotWatermark,
        run: ReconciliationRun,
    ) -> None:
        if self._executor is None:
            return
        supported = tuple(
            item for item in resolutions if self._executor.supports(item.type)
        )
        if not supported:
            return

        latest = self._internal_snapshots.capture(
            account_id=account_id,
            scope=scope,
        )
        if not _same_economic_cut(original_watermark, latest.watermark):
            stale = Mismatch(
                id=MismatchId.new(),
                run_id=run.id,
                type=MismatchType.STALE_RECONCILIATION,
                severity=MismatchSeverity.CRITICAL,
                entity_type="snapshot",
                entity_id="internal",
                internal_value=_watermark_evidence(original_watermark),
                external_value=_watermark_evidence(latest.watermark),
                detected_at=self._clock.now(),
            )
            self._repository.add_mismatch(stale)
            self._repository.checkpoint()
            if self._notifier is not None:
                self._notifier.critical_mismatch(run, count=1)
            raise StaleReconciliationError(
                "Internal economic evidence changed before recovery mutation."
            )

        by_id = {item.id: item for item in mismatches}
        for resolution in supported:
            mismatch = by_id[resolution.mismatch_id]
            resolution.mark_applying()
            self._repository.save_resolution(resolution)
            self._repository.checkpoint()
            try:
                self._executor.apply(
                    resolution=resolution,
                    mismatch=mismatch,
                    broker_snapshot=broker_snapshot,
                )
            except Exception:
                resolution.mark_failed(
                    completed_at=self._clock.now(),
                    verification_status="application_failed",
                )
                self._repository.save_resolution(resolution)
            self._repository.checkpoint()
                raise
            resolution.mark_applied(completed_at=self._clock.now())
            self._repository.save_resolution(resolution)
            self._repository.checkpoint()

    def _verify_applied(
        self,
        resolutions: tuple[Resolution, ...],
        initial: tuple[Mismatch, ...],
        remaining: tuple[Mismatch, ...],
    ) -> None:
        initial_by_id = {item.id: item for item in initial}
        remaining_keys = {(item.type, item.entity_id) for item in remaining}
        for resolution in resolutions:
            if resolution.status is not ResolutionStatus.APPLIED:
                continue
            mismatch = initial_by_id[resolution.mismatch_id]
            if (mismatch.type, mismatch.entity_id) in remaining_keys:
                resolution.mark_failed(
                    completed_at=self._clock.now(),
                    verification_status="mismatch_remains",
                )
            else:
                resolution.mark_verified(
                    verification_status="fresh_evidence_converged"
                )
            self._repository.save_resolution(resolution)
            self._repository.checkpoint()


def _same_economic_cut(
    original: SnapshotWatermark,
    latest: SnapshotWatermark,
) -> bool:
    if (
        original.internal_version is not None
        and latest.internal_version is not None
    ):
        return original.internal_version == latest.internal_version
    if (
        original.max_event_sequence is not None
        and latest.max_event_sequence is not None
    ):
        return original.max_event_sequence == latest.max_event_sequence
    return False


def _watermark_evidence(watermark: SnapshotWatermark) -> JsonEvidence:
    return {
        "captured_at": watermark.captured_at.isoformat(),
        "internal_version": watermark.internal_version,
        "max_event_sequence": watermark.max_event_sequence,
        "provider_as_of": (
            watermark.provider_as_of.isoformat()
            if watermark.provider_as_of is not None
            else None
        ),
        "provider_cursor": watermark.provider_cursor,
    }
