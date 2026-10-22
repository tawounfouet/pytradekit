"""PyTradeKit 0.5 production qualification evidence and release gate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QualificationStatus(StrEnum):
    """Status of one release qualification gate."""

    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


@dataclass(frozen=True, slots=True)
class QualificationGate:
    """One explicit release qualification requirement."""

    name: str
    status: QualificationStatus
    detail: str
    required: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe gate content."""

        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class ProductionQualificationReport:
    """Aggregated release evidence for PyTradeKit v0.5.0."""

    gates: tuple[QualificationGate, ...]

    @property
    def release_ready(self) -> bool:
        """Return True only when every required gate is PASS."""

        return all(
            gate.status is QualificationStatus.PASS
            for gate in self.gates
            if gate.required
        )

    @property
    def pending_required(self) -> tuple[str, ...]:
        """Return required gates that still lack evidence."""

        return tuple(
            gate.name
            for gate in self.gates
            if gate.required and gate.status is QualificationStatus.PENDING
        )

    @property
    def failed_required(self) -> tuple[str, ...]:
        """Return required gates that failed."""

        return tuple(
            gate.name
            for gate in self.gates
            if gate.required and gate.status is QualificationStatus.FAIL
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe release evidence."""

        return {
            "target_release": "v0.5.0",
            "release_ready": self.release_ready,
            "pending_required": list(self.pending_required),
            "failed_required": list(self.failed_required),
            "gates": [gate.to_dict() for gate in self.gates],
        }


@dataclass(frozen=True, slots=True)
class ProductionQualificationEvidence:
    """Input evidence collected by CI and real PAPER qualification."""

    ci_quality_gate: QualificationStatus = QualificationStatus.PENDING
    postgres_restart_e2e: QualificationStatus = QualificationStatus.PENDING
    crash_window_faults: QualificationStatus = QualificationStatus.PENDING
    graceful_shutdown: QualificationStatus = QualificationStatus.PENDING
    provider_429_5xx_semantics: QualificationStatus = QualificationStatus.PENDING
    real_paper_runtime_start_restart: QualificationStatus = QualificationStatus.PENDING
    real_paper_market_limit_cancel: QualificationStatus = QualificationStatus.PENDING
    real_paper_trade_updates: QualificationStatus = QualificationStatus.PENDING
    real_paper_uncertain_recovery: QualificationStatus = QualificationStatus.PENDING
    real_paper_cleanup: QualificationStatus = QualificationStatus.PENDING
    incident_runbook: QualificationStatus = QualificationStatus.PENDING


def evaluate_v050_release(
    evidence: ProductionQualificationEvidence,
) -> ProductionQualificationReport:
    """Evaluate the final v0.5.0 release gate without treating CI as PAPER evidence."""

    gates = (
        _gate(
            "ci_quality_gate",
            evidence.ci_quality_gate,
            "Typography, Ruff, mypy, architecture, tests, and package qualification.",
        ),
        _gate(
            "postgres_restart_e2e",
            evidence.postgres_restart_e2e,
            "Restart convergence and idempotent durable state on PostgreSQL.",
        ),
        _gate(
            "crash_window_faults",
            evidence.crash_window_faults,
            "Before-commit rollback and after-commit replay crash windows.",
        ),
        _gate(
            "graceful_shutdown",
            evidence.graceful_shutdown,
            "Admission drain, SIGTERM path, bounded shutdown, and forced-shutdown signal.",
        ),
        _gate(
            "provider_429_5xx_semantics",
            evidence.provider_429_5xx_semantics,
            "Reads fail safely and economic writes become UNCERTAIN without blind retry.",
        ),
        _gate(
            "real_paper_runtime_start_restart",
            evidence.real_paper_runtime_start_restart,
            "Real Alpaca PAPER startup, authenticated stream, stop, and restart.",
        ),
        _gate(
            "real_paper_market_limit_cancel",
            evidence.real_paper_market_limit_cancel,
            "Controlled MARKET, LIMIT, and CANCEL operations on PAPER.",
        ),
        _gate(
            "real_paper_trade_updates",
            evidence.real_paper_trade_updates,
            "Real private trade_updates observed for controlled PAPER operations.",
        ),
        _gate(
            "real_paper_uncertain_recovery",
            evidence.real_paper_uncertain_recovery,
            "Post-ack response loss recovered by client_order_id with one submit attempt.",
        ),
        _gate(
            "real_paper_cleanup",
            evidence.real_paper_cleanup,
            "Qualification finishes with the baseline PAPER position restored.",
        ),
        _gate(
            "incident_runbook",
            evidence.incident_runbook,
            "Operator runbooks cover readiness, provider faults, database faults, and recovery.",
        ),
    )
    return ProductionQualificationReport(gates=gates)


def _gate(
    name: str,
    status: QualificationStatus,
    detail: str,
) -> QualificationGate:
    return QualificationGate(
        name=name,
        status=status,
        detail=detail,
        required=True,
    )
