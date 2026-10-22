"""Unit tests for LOT-02 compliance evidence and certification models."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
    BrokerCapability,
    CertificationLevel,
    ComplianceCriticality,
    ComplianceEvidence,
    ComplianceEvidenceType,
    ComplianceRequirement,
    ComplianceResult,
    ComplianceStatus,
    EvidenceFreshnessReason,
    EvidenceSanitizer,
    StaleEvidencePolicy,
)
from pytradekit.runtime import RuntimeEnvironment
from tests.compliance_fakes import compliance_manifest


def test_c3_requirement_requires_paper_evidence() -> None:
    with pytest.raises(ValueError, match="C3 requirements must require PAPER evidence"):
        ComplianceRequirement(
            requirement_id="MARKET-PAPER",
            capability=BrokerCapability.MARKET_ORDER,
            level=CertificationLevel.C3_PAPER_QUALIFIED,
            description="Qualify MARKET against PAPER.",
            criticality=ComplianceCriticality.CRITICAL,
            applicable=True,
            evidence_type=ComplianceEvidenceType.INTEGRATION,
        )


def test_compliance_result_preserves_blocked_and_fail_as_distinct_statuses() -> None:
    now = datetime(2026, 10, 23, 10, tzinfo=UTC)
    blocked = ComplianceResult(
        scenario_id="blocked",
        status=ComplianceStatus.BLOCKED,
        started_at=now,
        completed_at=now,
        provider="provider-a",
        environment=RuntimeEnvironment.PAPER,
        reason="Environment unavailable.",
    )
    failed = replace(
        blocked,
        scenario_id="failed",
        status=ComplianceStatus.FAIL,
        reason="Observed behavior violated requirement.",
    )

    assert blocked.status is ComplianceStatus.BLOCKED
    assert failed.status is ComplianceStatus.FAIL


def test_evidence_sanitizer_redacts_secret_keys_markers_and_supplied_values() -> None:
    sanitizer = EvidenceSanitizer()
    secret = "paper-secret-value"

    sanitized = sanitizer.sanitize(
        {
            "api_key": secret,
            "authorization_header": f"Bearer {secret}",
            "nested": {"note": f"prefix {secret} suffix"},
        },
        sensitive_values=(secret,),
    )

    encoded = repr(sanitized)
    assert secret not in encoded
    assert "Bearer" not in encoded
    sanitizer.assert_safe(sanitized, sensitive_values=(secret,))


def test_stale_policy_invalidates_changed_adapter_and_sdk_evidence() -> None:
    now = datetime(2026, 10, 23, 10, tzinfo=UTC)
    manifest = compliance_manifest()
    evidence = ComplianceEvidence(
        evidence_id="run:market",
        scenario_id="market",
        provider=manifest.provider,
        environment=manifest.environment,
        commit_sha="abc123",
        adapter_version=manifest.adapter_version,
        contract_version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
        evidence_type=ComplianceEvidenceType.PAPER,
        captured_at=now,
        payload={"result": "pass"},
        sdk_name=manifest.sdk_name,
        sdk_version=manifest.sdk_version,
    )
    policy = StaleEvidencePolicy(max_age=timedelta(days=30))

    changed = replace(
        manifest,
        adapter_version="0.8.0a3",
        sdk_version="2.0.0",
    )
    freshness = policy.evaluate(
        evidence,
        manifest=changed,
        contract_version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
        now=now,
    )

    assert not freshness.is_current
    assert EvidenceFreshnessReason.ADAPTER_VERSION_MISMATCH in freshness.reasons
    assert EvidenceFreshnessReason.SDK_MISMATCH in freshness.reasons
