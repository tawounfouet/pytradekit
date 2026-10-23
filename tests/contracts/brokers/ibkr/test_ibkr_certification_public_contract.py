"""Public contract for IBKR LOT-06.7 certification surfaces."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_BASELINE_CERTIFICATION_LEVELS,
    IBKR_CERTIFICATION_ADAPTER_VERSION,
    IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES,
    IBKRComplianceScenarioExecutor,
    IBKREvidenceError,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    IBKRRetainedEvidenceFixture,
    build_ibkr_certification_manifest,
    build_ibkr_certification_run,
    build_ibkr_compliance_requirements,
    build_ibkr_compliance_scenarios,
    expected_ibkr_certification_levels,
    validate_ibkr_certification_run,
)


def test_ibkr_lot06_7_public_surface_is_exported() -> None:
    assert IBKR_CERTIFICATION_ADAPTER_VERSION == "0.8.0b8-lot06.7"
    assert IBKR_BASELINE_CERTIFICATION_LEVELS
    assert IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES
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
    assert callable(build_ibkr_certification_manifest)
    assert callable(build_ibkr_certification_run)
    assert callable(build_ibkr_compliance_requirements)
    assert callable(build_ibkr_compliance_scenarios)
    assert callable(expected_ibkr_certification_levels)
    assert callable(validate_ibkr_certification_run)
