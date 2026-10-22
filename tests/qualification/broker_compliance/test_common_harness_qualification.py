"""Deterministic LOT-02 qualification using the same harness for two providers."""

from datetime import UTC, datetime

from tests.compliance_fakes import (
    FakeProviderFixture,
    compliance_manifest,
    pass_executor,
)

from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
    PROVIDER_CAPABILITY_MANIFEST_VERSION,
    BrokerCapability,
    CertificationLevel,
    ComplianceCriticality,
    ComplianceEvidenceType,
    ComplianceHarness,
    ComplianceReportGenerator,
    ComplianceRequirement,
    ComplianceScenario,
    EvidenceSanitizer,
)
from pytradekit.testing import FakeClock


def test_common_harness_generates_equivalent_c3_reports_for_two_fixtures() -> None:
    requirement = ComplianceRequirement(
        requirement_id="COMMON-MARKET-PAPER",
        capability=BrokerCapability.MARKET_ORDER,
        level=CertificationLevel.C3_PAPER_QUALIFIED,
        description="MARKET PAPER behavior is proven.",
        criticality=ComplianceCriticality.CRITICAL,
        applicable=True,
        evidence_type=ComplianceEvidenceType.PAPER,
    )
    scenario = ComplianceScenario(
        scenario_id="COMMON-MARKET-PAPER",
        capability=BrokerCapability.MARKET_ORDER,
        preconditions=("PAPER account available",),
        action="execute common MARKET qualification",
        expected_result="provider-neutral MARKET semantics observed",
        failure_semantics="semantic mismatch is FAIL",
        cleanup="restore baseline",
        required_evidence=(ComplianceEvidenceType.PAPER,),
        requirement_ids=(requirement.requirement_id,),
    )
    harness = ComplianceHarness(
        contract=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
        requirements=(requirement,),
        scenarios=(scenario,),
        executors={scenario.scenario_id: pass_executor},
        sanitizer=EvidenceSanitizer(),
        report_generator=ComplianceReportGenerator(),
        clock=FakeClock.at(datetime(2026, 10, 23, 12, tzinfo=UTC)),
    )

    levels: list[CertificationLevel] = []
    for provider in ("provider-a", "provider-b"):
        run = harness.run(
            FakeProviderFixture(compliance_manifest(provider)),
            run_id=f"qualification-{provider}",
            commit_sha="shared-contract-commit",
            manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
        )
        record = next(
            item
            for item in run.report.capability_results
            if item.capability is BrokerCapability.MARKET_ORDER
        )
        levels.append(record.certification_level)
        assert run.report.complete
        assert run.evidence
        assert run.registry.entries

    assert levels == [
        CertificationLevel.C3_PAPER_QUALIFIED,
        CertificationLevel.C3_PAPER_QUALIFIED,
    ]
