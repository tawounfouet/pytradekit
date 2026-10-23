"""Unit tests for IBKR retained PAPER evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pytradekit.brokers.adapters.ibkr import (
    IBKREvidenceError,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    canonical_ibkr_evidence_sha256,
)
from pytradekit.brokers.compliance import BrokerCapability


def _bundle(
    *,
    c3_capabilities: tuple[BrokerCapability, ...] = (
        BrokerCapability.MARKET_ORDER,
    ),
) -> IBKRPaperEvidenceBundle:
    gates = {
        "ci_quality_gate": "PASS",
        "paper_market_order": "PASS",
        "paper_execution_details": "PASS",
        "paper_cancel_order": "PASS",
    }
    proofs = {
        BrokerCapability.MARKET_ORDER: {
            "submit_attempts": 1,
            "perm_id_present": True,
            "terminal_status": "Filled",
            "exec_id_present": True,
        },
        BrokerCapability.CANCEL_ORDER: {
            "cancel_attempts": 1,
            "requested": True,
            "final_status": "Cancelled",
        },
    }
    unsigned = IBKRPaperEvidenceBundle(
        provenance=IBKRPaperEvidenceProvenance(
            qualified_commit="a" * 40,
            artifact_name="ibkr-paper.json",
            artifact_json_sha256="0" * 64,
            source_ref="github-actions:ibkr-paper:test",
            workflow_run_id=1001,
            deterministic_ci_run_id=1000,
        ),
        captured_at=datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
        sdk_name="ib_async",
        sdk_version="2.1.0",
        account_mask="***1234",
        release_ready=True,
        controlled_probe_passed=True,
        gates=gates,
        c3_capabilities=c3_capabilities,
        proofs=proofs,
    )
    payload = unsigned.to_dict()
    provenance = payload["provenance"]
    assert isinstance(provenance, dict)
    provenance["artifact_json_sha256"] = (
        canonical_ibkr_evidence_sha256(payload)
    )
    return IBKRPaperEvidenceBundle.from_dict(payload)


def test_valid_market_order_c3_bundle_is_accepted() -> None:
    bundle = _bundle()

    assert bundle.paper_proof_passes(BrokerCapability.MARKET_ORDER)
    assert not bundle.paper_proof_passes(BrokerCapability.PARTIAL_FILL)
    assert bundle.provenance.artifact_json_sha256 == (
        canonical_ibkr_evidence_sha256(bundle.to_dict())
    )


def test_claimed_c3_without_required_gate_fails_closed() -> None:
    with pytest.raises(IBKREvidenceError, match="without sufficient"):
        IBKRPaperEvidenceBundle(
            provenance=IBKRPaperEvidenceProvenance(
                qualified_commit="a" * 40,
                artifact_name="ibkr-paper.json",
                artifact_json_sha256="b" * 64,
                source_ref="manual:ibkr-paper:20261023",
            ),
            captured_at=datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
            sdk_name="ib_async",
            sdk_version="2.1.0",
            account_mask="***1234",
            release_ready=True,
            controlled_probe_passed=True,
            gates={
                "ci_quality_gate": "PASS",
                "paper_market_order": "PASS",
            },
            c3_capabilities=(BrokerCapability.MARKET_ORDER,),
            proofs={
                BrokerCapability.MARKET_ORDER: {
                    "submit_attempts": 1,
                    "perm_id_present": True,
                    "terminal_status": "Filled",
                    "exec_id_present": True,
                }
            },
        )


def test_wrong_sdk_version_is_rejected() -> None:
    with pytest.raises(IBKREvidenceError, match="SDK version"):
        IBKRPaperEvidenceBundle(
            provenance=IBKRPaperEvidenceProvenance(
                qualified_commit="a" * 40,
                artifact_name="ibkr-paper.json",
                artifact_json_sha256="b" * 64,
                source_ref="manual:ibkr-paper:20261023",
            ),
            captured_at=datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
            sdk_name="ib_async",
            sdk_version="9.9.9",
            account_mask="***1234",
            release_ready=False,
            controlled_probe_passed=False,
            gates={},
            c3_capabilities=(),
            proofs={},
        )


def test_evidence_round_trip_preserves_c3_claims() -> None:
    bundle = _bundle(
        c3_capabilities=(
            BrokerCapability.MARKET_ORDER,
            BrokerCapability.CANCEL_ORDER,
        )
    )

    restored = IBKRPaperEvidenceBundle.from_dict(bundle.to_dict())

    assert restored.c3_capabilities == bundle.c3_capabilities
    assert restored.paper_proof_passes(BrokerCapability.CANCEL_ORDER)


def test_tampered_retained_evidence_is_rejected() -> None:
    bundle = _bundle()
    payload = bundle.to_dict()
    proofs = payload["proofs"]
    assert isinstance(proofs, dict)
    market = proofs[BrokerCapability.MARKET_ORDER.value]
    assert isinstance(market, dict)
    market["terminal_status"] = "Cancelled"

    with pytest.raises(IBKREvidenceError, match="SHA-256"):
        IBKRPaperEvidenceBundle.from_dict(payload)


def test_canonical_evidence_sha256_is_stable() -> None:
    one = canonical_ibkr_evidence_sha256(
        {"b": 2, "a": {"z": True, "x": 1}}
    )
    two = canonical_ibkr_evidence_sha256(
        {"a": {"x": 1, "z": True}, "b": 2}
    )

    assert one == two
    assert len(one) == 64
