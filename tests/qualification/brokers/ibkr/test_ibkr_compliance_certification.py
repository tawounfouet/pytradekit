"""Qualification tests for IBKR LOT-06.7 compliance certification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pytradekit.brokers.compliance import (
    BrokerCapability,
    CertificationLevel,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    build_ibkr_certification_run,
)

_NOW = datetime(2026, 10, 23, 12, 30, tzinfo=UTC)
_COMMIT = "c" * 40


def _evidence() -> IBKRPaperEvidenceBundle:
    return IBKRPaperEvidenceBundle(
        provenance=IBKRPaperEvidenceProvenance(
            qualified_commit=_COMMIT,
            artifact_name="ibkr-paper-real.json",
            artifact_json_sha256="d" * 64,
            source_ref="manual:ibkr-paper:qualification",
        ),
        captured_at=_NOW,
        sdk_name="ib_async",
        sdk_version="2.1.0",
        account_mask="***4321",
        release_ready=True,
        controlled_probe_passed=True,
        gates={
            "ci_quality_gate": "PASS",
            "paper_market_order": "PASS",
            "paper_execution_details": "PASS",
            "paper_cancel_order": "PASS",
        },
        c3_capabilities=(
            BrokerCapability.MARKET_ORDER,
            BrokerCapability.CANCEL_ORDER,
        ),
        proofs={
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
        },
    )


def _levels(run: object) -> dict[BrokerCapability, CertificationLevel]:
    report = getattr(run, "report")
    return {
        item.capability: item.certification_level
        for item in report.capability_results
    }


def test_without_real_paper_evidence_all_declared_capabilities_stop_at_c2() -> None:
    run = build_ibkr_certification_run(
        commit_sha=_COMMIT,
        captured_at=_NOW,
        evidence=None,
    )

    levels = _levels(run)

    assert set(levels.values()) == {
        CertificationLevel.C2_INTEGRATION_QUALIFIED
    }
    assert run.report.complete
    assert all(
        item.evidence_type.value == "INTEGRATION"
        for item in run.evidence
    )


def test_retained_real_paper_evidence_promotes_only_explicit_claims() -> None:
    run = build_ibkr_certification_run(
        commit_sha=_COMMIT,
        captured_at=_NOW,
        evidence=_evidence(),
    )

    levels = _levels(run)

    assert (
        levels[BrokerCapability.MARKET_ORDER]
        is CertificationLevel.C3_PAPER_QUALIFIED
    )
    assert (
        levels[BrokerCapability.CANCEL_ORDER]
        is CertificationLevel.C3_PAPER_QUALIFIED
    )
    assert (
        levels[BrokerCapability.PARTIAL_FILL]
        is CertificationLevel.C2_INTEGRATION_QUALIFIED
    )
    assert (
        levels[BrokerCapability.RECONNECT_RECOVERY]
        is CertificationLevel.C2_INTEGRATION_QUALIFIED
    )
    assert run.report.complete


def test_evidence_commit_must_match_certification_target() -> None:
    with pytest.raises(ValueError, match="does not match"):
        build_ibkr_certification_run(
            commit_sha="e" * 40,
            captured_at=_NOW,
            evidence=_evidence(),
        )
