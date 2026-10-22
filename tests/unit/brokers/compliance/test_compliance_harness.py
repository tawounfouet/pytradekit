"""Unit qualification for the common LOT-02 compliance harness."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
    PROVIDER_CAPABILITY_MANIFEST_VERSION,
    BrokerCapability,
    CertificationLevel,
    ComplianceCriticality,
    ComplianceEvidenceType,
    ComplianceHarness,
    ComplianceObservation,
    ComplianceReportGenerator,
    ComplianceRequirement,
    ComplianceRun,
    ComplianceScenario,
    ComplianceScenarioExecutor,
    ComplianceStatus,
    EvidenceSanitizer,
    ProviderFixture,
    StaleEvidencePolicy,
)
from pytradekit.testing import FakeClock
from tests.compliance_fakes import (
    FakeProviderFixture,
    compliance_manifest,
    pass_executor,
)


def _requirements() -> tuple[ComplianceRequirement, ...]:
    return (
        ComplianceRequirement(
            requirement_id="MARKET-C1",
            capability=BrokerCapability.MARKET_ORDER,
            level=CertificationLevel.C1_IMPLEMENTED,
            description="MARKET adapter implementation exists.",
            criticality=ComplianceCriticality.HIGH,
            applicable=True,
            evidence_type=ComplianceEvidenceType.IMPLEMENTATION,
        ),
        ComplianceRequirement(
            requirement_id="MARKET-C2",
            capability=BrokerCapability.MARKET_ORDER,
            level=CertificationLevel.C2_INTEGRATION_QUALIFIED,
            description="MARKET integration behavior passes.",
            criticality=ComplianceCriticality.HIGH,
            applicable=True,
            evidence_type=ComplianceEvidenceType.INTEGRATION,
        ),
        ComplianceRequirement(
            requirement_id="MARKET-C3",
            capability=BrokerCapability.MARKET_ORDER,
            level=CertificationLevel.C3_PAPER_QUALIFIED,
            description="MARKET is qualified against PAPER.",
            criticality=ComplianceCriticality.CRITICAL,
            applicable=True,
            evidence_type=ComplianceEvidenceType.PAPER,
        ),
    )


def _scenarios() -> tuple[ComplianceScenario, ...]:
    return (
        ComplianceScenario(
            scenario_id="MARKET-IMPLEMENTATION",
            capability=BrokerCapability.MARKET_ORDER,
            preconditions=("adapter constructed",),
            action="inspect canonical execution surface",
            expected_result="implementation is available",
            failure_semantics="missing implementation fails C1",
            cleanup="restore fixture baseline",
            required_evidence=(ComplianceEvidenceType.IMPLEMENTATION,),
            requirement_ids=("MARKET-C1",),
        ),
        ComplianceScenario(
            scenario_id="MARKET-INTEGRATION",
            capability=BrokerCapability.MARKET_ORDER,
            preconditions=("deterministic fixture available",),
            action="execute deterministic integration behavior",
            expected_result="canonical outcome is observed",
            failure_semantics="semantic mismatch fails C2",
            cleanup="restore fixture baseline",
            required_evidence=(ComplianceEvidenceType.INTEGRATION,),
            requirement_ids=("MARKET-C2",),
        ),
        ComplianceScenario(
            scenario_id="MARKET-PAPER",
            capability=BrokerCapability.MARKET_ORDER,
            preconditions=("PAPER environment available",),
            action="submit one controlled PAPER MARKET scenario",
            expected_result="real provider fact is observed",
            failure_semantics="behavior mismatch fails C3",
            cleanup="restore PAPER baseline",
            required_evidence=(ComplianceEvidenceType.PAPER,),
            requirement_ids=("MARKET-C3",),
        ),
    )


def _harness(
    *,
    executors: dict[str, ComplianceScenarioExecutor] | None = None,
) -> ComplianceHarness:
    scenarios = _scenarios()
    effective: dict[str, ComplianceScenarioExecutor] = {
        scenario.scenario_id: pass_executor
        for scenario in scenarios
    }
    if executors is not None:
        effective = executors
    return ComplianceHarness(
        contract=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
        requirements=_requirements(),
        scenarios=scenarios,
        executors=effective,
        sanitizer=EvidenceSanitizer(),
        report_generator=ComplianceReportGenerator(),
        clock=FakeClock.at(datetime(2026, 10, 23, 10, tzinfo=UTC)),
    )


def _market_level(run: ComplianceRun) -> CertificationLevel:
    record = next(
        item
        for item in run.report.capability_results
        if item.capability is BrokerCapability.MARKET_ORDER
    )
    return record.certification_level


def test_same_harness_qualifies_two_provider_fixtures_without_provider_branches() -> None:
    harness = _harness()
    provider_a = FakeProviderFixture(compliance_manifest("provider-a"))
    provider_b = FakeProviderFixture(compliance_manifest("provider-b"))

    run_a = harness.run(
        provider_a,
        run_id="run-a",
        commit_sha="commit-a",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )
    run_b = harness.run(
        provider_b,
        run_id="run-b",
        commit_sha="commit-b",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )

    assert _market_level(run_a) is CertificationLevel.C3_PAPER_QUALIFIED
    assert _market_level(run_b) is CertificationLevel.C3_PAPER_QUALIFIED
    assert provider_a.cleanup_calls == 3
    assert provider_b.cleanup_calls == 3


def test_missing_executor_is_blocked_and_cannot_produce_c3() -> None:
    harness = _harness(executors={})
    fixture = FakeProviderFixture(compliance_manifest())

    run = harness.run(
        fixture,
        run_id="blocked-run",
        commit_sha="commit",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )

    assert all(
        result.status is ComplianceStatus.BLOCKED
        for result in run.report.scenario_results
    )
    assert _market_level(run) is CertificationLevel.C0_DEFINED
    assert not run.report.complete


def test_cleanup_failure_blocks_otherwise_passing_scenario() -> None:
    harness = _harness()
    fixture = FakeProviderFixture(
        compliance_manifest(),
        cleanup_should_fail=True,
    )

    run = harness.run(
        fixture,
        run_id="cleanup-run",
        commit_sha="commit",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )

    assert run.report.scenario_results[0].status is ComplianceStatus.BLOCKED
    assert not run.report.complete


def test_fail_remains_fail_and_is_not_collapsed_into_blocked() -> None:
    scenarios = _scenarios()

    def fail_executor(
        fixture: ProviderFixture,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        del fixture
        return ComplianceObservation(
            status=ComplianceStatus.FAIL,
            evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
            payload={"observed": "unexpected"},
            reason=f"{scenario.scenario_id} violated the requirement.",
        )

    harness = _harness(
        executors={scenario.scenario_id: fail_executor for scenario in scenarios},
    )
    run = harness.run(
        FakeProviderFixture(compliance_manifest()),
        run_id="fail-run",
        commit_sha="commit",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )

    assert all(
        result.status is ComplianceStatus.FAIL
        for result in run.report.scenario_results
    )
    assert _market_level(run) is CertificationLevel.C0_DEFINED


def test_harness_artifact_is_secret_safe() -> None:
    scenarios = _scenarios()
    secret = "provider-super-secret"

    def secret_executor(
        fixture: ProviderFixture,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        del fixture
        return ComplianceObservation(
            status=ComplianceStatus.PASS,
            evidence_type=scenario.required_evidence[0],
            payload={
                "api_key": secret,
                "message": f"Bearer {secret}",
                "nested": {"value": secret},
            },
        )

    harness = _harness(
        executors={scenario.scenario_id: secret_executor for scenario in scenarios},
    )
    run = harness.run(
        FakeProviderFixture(compliance_manifest()),
        run_id="secret-run",
        commit_sha="commit",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
        sensitive_values=(secret,),
    )

    encoded = run.to_json()
    assert secret not in encoded
    assert "Bearer" not in encoded


def test_registry_rejects_stale_evidence_after_adapter_change() -> None:
    harness = _harness()
    manifest = compliance_manifest()
    run = harness.run(
        FakeProviderFixture(manifest),
        run_id="current-run",
        commit_sha="commit",
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )
    changed = replace(manifest, adapter_version="0.8.0a3")

    current = run.registry.find_current(
        provider=manifest.provider,
        environment=manifest.environment,
        capability=BrokerCapability.MARKET_ORDER,
        contract_version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE.version,
        manifest=changed,
        evidence_by_ref=run.evidence_by_ref,
        stale_policy=StaleEvidencePolicy(),
        now=datetime(2026, 10, 23, 10, tzinfo=UTC),
    )

    assert current is None
