"""Unit tests for the final v0.5.0 release gate."""

from pytradekit.runtime.qualification import (
    ProductionQualificationEvidence,
    QualificationStatus,
    evaluate_v050_release,
)


def test_ci_only_evidence_never_marks_v050_release_ready() -> None:
    evidence = ProductionQualificationEvidence(
        ci_quality_gate=QualificationStatus.PASS,
        postgres_restart_e2e=QualificationStatus.PASS,
        crash_window_faults=QualificationStatus.PASS,
        graceful_shutdown=QualificationStatus.PASS,
        provider_429_5xx_semantics=QualificationStatus.PASS,
        incident_runbook=QualificationStatus.PASS,
    )

    report = evaluate_v050_release(evidence)

    assert report.release_ready is False
    assert "real_paper_runtime_start_restart" in report.pending_required
    assert "real_paper_market_limit_cancel" in report.pending_required


def test_all_required_evidence_marks_v050_release_ready() -> None:
    passed = QualificationStatus.PASS
    evidence = ProductionQualificationEvidence(
        ci_quality_gate=passed,
        postgres_restart_e2e=passed,
        crash_window_faults=passed,
        graceful_shutdown=passed,
        provider_429_5xx_semantics=passed,
        real_paper_runtime_start_restart=passed,
        real_paper_market_limit_cancel=passed,
        real_paper_trade_updates=passed,
        real_paper_uncertain_recovery=passed,
        real_paper_cleanup=passed,
        incident_runbook=passed,
    )

    assert evaluate_v050_release(evidence).release_ready is True
