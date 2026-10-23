"""Public contract for IBKR LOT-06.7 compliance certification."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_BASELINE_CERTIFICATION_LEVELS,
    IBKR_COMPLIANCE_ADAPTER_VERSION,
    IBKR_PAPER_EVIDENCE_SCHEMA_VERSION,
    IBKRComplianceScenarioExecutor,
    IBKREvidenceError,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    IBKRRetainedEvidenceFixture,
    build_ibkr_certification_run,
    build_ibkr_compliance_manifest,
    build_ibkr_compliance_requirements,
    build_ibkr_compliance_scenarios,
    canonical_ibkr_evidence_sha256,
    validate_ibkr_certification_run,
)


def test_ibkr_lot06_7_public_surface_is_exported() -> None:
    assert IBKR_COMPLIANCE_ADAPTER_VERSION == "0.8.0b8-lot06.7"
    assert IBKR_PAPER_EVIDENCE_SCHEMA_VERSION == "1"
    assert IBKR_BASELINE_CERTIFICATION_LEVELS
    assert IBKRComplianceScenarioExecutor.__name__ == (
        "IBKRComplianceScenarioExecutor"
    )
    assert issubclass(IBKREvidenceError, ValueError)
    assert IBKRPaperEvidenceBundle.__name__ == "IBKRPaperEvidenceBundle"
    assert IBKRPaperEvidenceProvenance.__name__ == (
        "IBKRPaperEvidenceProvenance"
    )
    assert IBKRRetainedEvidenceFixture.__name__ == (
        "IBKRRetainedEvidenceFixture"
    )
    assert callable(build_ibkr_certification_run)
    assert callable(build_ibkr_compliance_manifest)
    assert callable(build_ibkr_compliance_requirements)
    assert callable(build_ibkr_compliance_scenarios)
    assert callable(canonical_ibkr_evidence_sha256)
    assert callable(validate_ibkr_certification_run)
