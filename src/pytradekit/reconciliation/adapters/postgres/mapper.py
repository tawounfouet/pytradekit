"""Mapping between reconciliation domain evidence and PostgreSQL rows."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    JsonEvidence,
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    Resolution,
    ResolutionId,
    ResolutionStatus,
    ResolutionType,
    SnapshotWatermark,
    StateConfidence,
)
from pytradekit.shared import CorrelationId

from .models import (
    ReconciliationMismatchModel,
    ReconciliationResolutionModel,
    ReconciliationRunModel,
)


def watermark_to_json(watermark: SnapshotWatermark | None) -> dict[str, object] | None:
    if watermark is None:
        return None
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


def watermark_from_json(value: dict[str, object] | None) -> SnapshotWatermark | None:
    if value is None:
        return None
    captured_at = value.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("Persisted watermark captured_at is invalid.")
    provider_as_of_raw = value.get("provider_as_of")
    internal_version_raw = value.get("internal_version")
    max_event_sequence_raw = value.get("max_event_sequence")
    provider_cursor_raw = value.get("provider_cursor")
    return SnapshotWatermark(
        captured_at=datetime.fromisoformat(captured_at),
        internal_version=(
            internal_version_raw if isinstance(internal_version_raw, int) else None
        ),
        max_event_sequence=(
            max_event_sequence_raw if isinstance(max_event_sequence_raw, int) else None
        ),
        provider_as_of=(
            datetime.fromisoformat(provider_as_of_raw)
            if isinstance(provider_as_of_raw, str)
            else None
        ),
        provider_cursor=(
            provider_cursor_raw if isinstance(provider_cursor_raw, str) else None
        ),
    )


def run_to_values(run: ReconciliationRun) -> dict[str, object]:
    return {
        "id": run.id.value,
        "account_id": run.account_id.value,
        "scope": run.scope.value,
        "trigger": run.trigger.value,
        "status": run.status.value,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "internal_watermark": watermark_to_json(run.internal_watermark),
        "broker_watermark": watermark_to_json(run.broker_watermark),
        "mismatch_count": run.mismatch_count,
        "critical_mismatch_count": run.critical_mismatch_count,
        "result_status": run.result_status.value if run.result_status is not None else None,
        "state_confidence": run.confidence.value if run.confidence is not None else None,
        "correlation_id": run.correlation_id.value,
        "version": run.version,
    }


def run_from_model(row: ReconciliationRunModel) -> ReconciliationRun:
    return ReconciliationRun(
        id=ReconciliationRunId(row.id),
        account_id=AccountId(row.account_id),
        scope=ReconciliationScope(row.scope),
        trigger=ReconciliationTrigger(row.trigger),
        status=ReconciliationRunStatus(row.status),
        started_at=row.started_at,
        completed_at=row.completed_at,
        internal_watermark=watermark_from_json(row.internal_watermark),
        broker_watermark=watermark_from_json(row.broker_watermark),
        mismatch_count=row.mismatch_count,
        critical_mismatch_count=row.critical_mismatch_count,
        result_status=(
            ConsistencyStatus(row.result_status) if row.result_status is not None else None
        ),
        confidence=(
            StateConfidence(row.state_confidence)
            if row.state_confidence is not None
            else None
        ),
        correlation_id=CorrelationId(row.correlation_id),
        version=row.version,
    )


def mismatch_to_values(value: Mismatch) -> dict[str, object]:
    return {
        "id": value.id.value,
        "run_id": value.run_id.value,
        "type": value.type.value,
        "severity": value.severity.value,
        "entity_type": value.entity_type,
        "entity_id": value.entity_id,
        "internal_value_json": value.internal_value,
        "external_value_json": value.external_value,
        "detected_at": value.detected_at,
        "resolved_at": None,
    }


def mismatch_from_model(row: ReconciliationMismatchModel) -> Mismatch:
    return Mismatch(
        id=MismatchId(row.id),
        run_id=ReconciliationRunId(row.run_id),
        type=MismatchType(row.type),
        severity=MismatchSeverity(row.severity),
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        internal_value=cast(JsonEvidence | None, row.internal_value_json),
        external_value=cast(JsonEvidence | None, row.external_value_json),
        detected_at=row.detected_at,
    )


def resolution_to_values(value: Resolution) -> dict[str, object]:
    return {
        "id": value.id.value,
        "run_id": value.run_id.value,
        "mismatch_id": value.mismatch_id.value,
        "type": value.type.value,
        "status": value.status.value,
        "reason": value.reason,
        "actor": value.actor,
        "started_at": value.started_at,
        "completed_at": value.completed_at,
        "verification_json": (
            {"status": value.verification_status}
            if value.verification_status is not None
            else None
        ),
        "correlation_id": value.correlation_id.value,
    }


def resolution_from_model(row: ReconciliationResolutionModel) -> Resolution:
    verification_status: str | None = None
    if row.verification_json is not None:
        status = row.verification_json.get("status")
        verification_status = status if isinstance(status, str) else None
    return Resolution(
        id=ResolutionId(row.id),
        run_id=ReconciliationRunId(row.run_id),
        mismatch_id=MismatchId(row.mismatch_id),
        type=ResolutionType(row.type),
        reason=row.reason,
        actor=row.actor,
        started_at=row.started_at,
        correlation_id=CorrelationId(row.correlation_id),
        status=ResolutionStatus(row.status),
        completed_at=row.completed_at,
        verification_status=verification_status,
    )
