"""LOT-02 broker compliance evidence fitness functions."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
    BrokerCapability,
    CertificationLevel,
    ComplianceCriticality,
    ComplianceEvidence,
    ComplianceEvidenceType,
    ComplianceRequirement,
    EvidenceSanitizer,
    StaleEvidencePolicy,
)
from pytradekit.testing import compliance_manifest


def test_ff_057_c3_requires_real_paper_evidence_type() -> None:
    with pytest.raises(ValueError, match="C3 requirements must require PAPER evidence"):
        ComplianceRequirement(
            requirement_id="C3-NOT-PAPER",
            capability=BrokerCapability.MARKET_ORDER,
            level=CertificationLevel.C3_PAPER_QUALIFIED,
            description="C3 must not accept deterministic-only evidence.",
            criticality=ComplianceCriticality.CRITICAL,
            applicable=True,
            evidence_type=ComplianceEvidenceType.INTEGRATION,
        )


def test_ff_058_stale_evidence_cannot_certify_changed_adapter() -> None:
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    manifest = compliance_manifest()
    evidence = ComplianceEvidence(
        evidence_id="run:paper",
        scenario_id="paper",
        provider=manifest.provider,
        environment=manifest.environment,
        commit_sha="qualified-commit",
        adapter_version=manifest.adapter_version,
        contract_version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
        evidence_type=ComplianceEvidenceType.PAPER,
        captured_at=now,
        payload={"status": "PASS"},
        sdk_name=manifest.sdk_name,
        sdk_version=manifest.sdk_version,
    )
    changed_manifest = replace(manifest, adapter_version="changed-adapter")

    freshness = StaleEvidencePolicy().evaluate(
        evidence,
        manifest=changed_manifest,
        contract_version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
        now=now,
    )

    assert not freshness.is_current


def test_ff_059_compliance_artifacts_must_pass_secret_scan() -> None:
    sanitizer = EvidenceSanitizer()
    secret = "do-not-retain"

    payload = sanitizer.sanitize(
        {
            "api_key": secret,
            "detail": f"Bearer {secret}",
            "nested": {"raw": secret},
        },
        sensitive_values=(secret,),
    )

    sanitizer.assert_safe(payload, sensitive_values=(secret,))
    assert secret not in repr(payload)
