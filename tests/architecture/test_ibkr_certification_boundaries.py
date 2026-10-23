"""Architecture fitness functions for IBKR LOT-06.7 certification."""

from pathlib import Path

_EVIDENCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/compliance_evidence.py"
)
_COMPLIANCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/compliance.py"
)
_PROBE = Path("scripts/qualify_ibkr_real_paper.py")
_CERTIFY = Path("scripts/qualify_ibkr_0_8_certification.py")
_WORKFLOW = Path(".github/workflows/ibkr-real-paper.yml")


def test_real_paper_probe_uses_canonical_execution_adapter() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert "build_ibkr_execution_adapter" in source
    assert ".placeOrder(" not in source
    assert ".cancelOrder(" not in source
    assert "time.sleep(" not in source


def test_real_paper_probe_requires_explicit_economic_write_ack() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert "PYTRADEKIT_IBKR_ORDER_PROBE_ACK" in source
    assert "I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED" in source
    assert "IBKRPaperRuntimeProfile.from_environment()" in source


def test_real_paper_artifact_masks_account_identity() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert '"account": profile.masked_account_id' in source
    assert '"account": profile.expected_account_id' not in source


def test_certification_requires_retained_paper_evidence_for_c3() -> None:
    source = _COMPLIANCE.read_text(encoding="utf-8")
    evidence = _EVIDENCE.read_text(encoding="utf-8")

    assert "CertificationLevel.C3_PAPER_QUALIFIED" in source
    assert "paper_proof_passes" in source
    assert "real_provider_used" in evidence
    assert "controlled_probe_passed" in evidence
    assert "cleanup_passed" in evidence


def test_partial_fill_is_not_c3_eligible_without_real_partial_fill() -> None:
    source = _COMPLIANCE.read_text(encoding="utf-8")

    assert "capability is not BrokerCapability.PARTIAL_FILL" in source


def test_deterministic_ci_has_no_retained_ibkr_paper_evidence() -> None:
    evidence_dir = Path("docs/qualification/evidence/ibkr")

    if evidence_dir.exists():
        assert list(evidence_dir.glob("*.json")) == []


def test_real_paper_workflow_is_manual_only() -> None:
    source = _WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in source
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "qualify_ibkr_real_paper.py" in source
    assert "--require-c3-target" in source


def test_certification_script_never_manufactures_provider_proof() -> None:
    source = _CERTIFY.read_text(encoding="utf-8")

    assert "IBKRPaperEvidenceBundle.from_dict" in source
    assert "real_provider_used=True" not in source
    assert "controlled_probe_passed=True" not in source
