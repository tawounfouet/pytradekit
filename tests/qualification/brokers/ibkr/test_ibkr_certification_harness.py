"""Qualification tests for IBKR LOT-06.7 certification harness."""

from datetime import UTC, datetime

from pytradekit.brokers.compliance import (
    CertificationLevel,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKR_BASELINE_CERTIFICATION_LEVELS,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    build_ibkr_certification_run,
)


def test_deterministic_ci_cannot_create_ibkr_c3_evidence() -> None:
    evidence = IBKRPaperEvidenceBundle(
        provenance=IBKRPaperEvidenceProvenance(
            source_release="0.8.0b8",
            qualified_commit="deterministic-ci",
            artifact_name="no-real-provider-artifact",
            artifact_json_sha256="c" * 64,
            deterministic_ci_run_id=367,
        ),
        captured_at=datetime(2026, 10, 23, 12, 10, tzinfo=UTC),
        sdk_name="ib_async",
        sdk_version="2.1.0",
        real_provider_used=False,
        controlled_probe_passed=False,
        cleanup_passed=False,
        gates={"ci_quality_gate": "PASS"},
        proofs={},
    )

    run = build_ibkr_certification_run(evidence)
    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }

    assert observed == dict(IBKR_BASELINE_CERTIFICATION_LEVELS)
    assert all(
        level is CertificationLevel.C2_INTEGRATION_QUALIFIED
        for level in observed.values()
    )
