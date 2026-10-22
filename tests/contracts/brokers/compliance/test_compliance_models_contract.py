"""Public contract tests for LOT-02 compliance models."""

from pytradekit.brokers.compliance import (
    CertificationRegistry,
    CertifiedCapability,
    ComplianceEvidence,
    ComplianceHarness,
    ComplianceReport,
    ComplianceReportGenerator,
    ComplianceRequirement,
    ComplianceResult,
    ComplianceScenario,
    ComplianceStatus,
    EvidenceSanitizer,
    StaleEvidencePolicy,
)


def test_lot02_types_are_available_from_public_compliance_surface() -> None:
    exported = (
        ComplianceRequirement,
        ComplianceScenario,
        ComplianceResult,
        ComplianceEvidence,
        ComplianceReport,
        CertifiedCapability,
        ComplianceHarness,
        EvidenceSanitizer,
        CertificationRegistry,
        StaleEvidencePolicy,
    )

    assert all(value.__module__.startswith("pytradekit.brokers.compliance") for value in exported)


def test_compliance_status_contract_is_explicit() -> None:
    assert tuple(status.value for status in ComplianceStatus) == (
        "PASS",
        "FAIL",
        "BLOCKED",
        "NOT_APPLICABLE",
    )


def test_report_generation_is_a_public_compliance_service() -> None:
    assert ComplianceReportGenerator.__module__ == "pytradekit.brokers.compliance.report"
