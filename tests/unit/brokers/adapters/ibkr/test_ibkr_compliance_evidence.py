"""Unit tests for retained IBKR PAPER compliance evidence."""

from datetime import UTC, datetime

import pytest

from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.brokers.adapters.ibkr import (
    IBKREvidenceError,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
)

_CAPTURED = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
_SHA = "a" * 64


def _provenance() -> IBKRPaperEvidenceProvenance:
    return IBKRPaperEvidenceProvenance(
        source_release="0.8.0b8",
        qualified_commit="abc123",
        artifact_name="pytradekit-ibkr-paper-qualification",
        artifact_json_sha256=_SHA,
        workflow_run_id=123,
        deterministic_ci_run_id=367,
    )


def _full_proofs() -> dict[BrokerCapability, dict[str, object]]:
    return {
        BrokerCapability.ACCOUNT_QUERY: {
            "account_ready": True,
            "managed_account_match": True,
            "cash_present": True,
            "equity_present": True,
            "buying_power_present": True,
        },
        BrokerCapability.ORDER_QUERY: {
            "query_observed": True,
            "perm_id_present": True,
            "status_observed": True,
        },
        BrokerCapability.MARKET_ORDER: {
            "submitted": True,
            "submit_attempts": 1,
            "filled": True,
            "perm_id_present": True,
            "exec_id_present": True,
        },
        BrokerCapability.LIMIT_ORDER: {
            "submitted": True,
            "submit_attempts": 1,
            "limit_price_present": True,
            "market_rule_checked": True,
        },
        BrokerCapability.CANCEL_ORDER: {
            "requested": True,
            "cancel_attempts": 1,
            "terminal_cancelled": True,
        },
        BrokerCapability.POSITION_QUERY: {
            "baseline_observed": True,
            "baseline_restored": True,
        },
        BrokerCapability.BALANCE_QUERY: {
            "cash_present": True,
            "equity_present": True,
            "buying_power_present": True,
        },
        BrokerCapability.CLIENT_ORDER_REFERENCE: {
            "order_ref_present": True,
            "round_trip_match": True,
            "submit_attempts": 1,
        },
        BrokerCapability.EXECUTION_FACTS: {
            "exec_details_count": 1,
            "exec_id_present": True,
            "perm_id_present": True,
            "fill_quantity_positive": True,
        },
        BrokerCapability.RECONNECT_RECOVERY: {
            "disconnect_observed": True,
            "reconnect_observed": True,
            "post_reconnect_account_query": True,
            "economic_replay": False,
        },
    }


def _bundle(
    *,
    real_provider_used: bool = True,
    controlled_probe_passed: bool = True,
    cleanup_passed: bool = True,
) -> IBKRPaperEvidenceBundle:
    return IBKRPaperEvidenceBundle(
        provenance=_provenance(),
        captured_at=_CAPTURED,
        sdk_name="ib_async",
        sdk_version="2.1.0",
        real_provider_used=real_provider_used,
        controlled_probe_passed=controlled_probe_passed,
        cleanup_passed=cleanup_passed,
        gates={
            "ci_quality_gate": "PASS",
            "real_paper_preflight": "PASS",
            "real_paper_orders": "PASS",
            "real_paper_callbacks": "PASS",
            "real_paper_cleanup": "PASS",
            "real_paper_reconnect": "PASS",
        },
        proofs=_full_proofs(),
    )


def test_full_bundle_supports_c3_for_eligible_capabilities() -> None:
    bundle = _bundle()

    for capability in _full_proofs():
        assert bundle.paper_proof_passes(capability)

    assert not bundle.paper_proof_passes(
        BrokerCapability.PARTIAL_FILL
    )


def test_non_provider_bundle_can_never_support_c3() -> None:
    bundle = _bundle(real_provider_used=False)

    assert not bundle.paper_proof_passes(
        BrokerCapability.MARKET_ORDER
    )


def test_cleanup_failure_blocks_all_paper_proofs() -> None:
    bundle = _bundle(cleanup_passed=False)

    assert not bundle.paper_proof_passes(
        BrokerCapability.MARKET_ORDER
    )
    assert not bundle.paper_proof_passes(
        BrokerCapability.ACCOUNT_QUERY
    )


def test_market_order_requires_one_submit_attempt() -> None:
    proofs = _full_proofs()
    proofs[BrokerCapability.MARKET_ORDER]["submit_attempts"] = 2
    bundle = IBKRPaperEvidenceBundle(
        provenance=_provenance(),
        captured_at=_CAPTURED,
        sdk_name="ib_async",
        sdk_version="2.1.0",
        real_provider_used=True,
        controlled_probe_passed=True,
        cleanup_passed=True,
        gates={
            "ci_quality_gate": "PASS",
            "real_paper_preflight": "PASS",
            "real_paper_orders": "PASS",
            "real_paper_callbacks": "PASS",
            "real_paper_cleanup": "PASS",
            "real_paper_reconnect": "PASS",
        },
        proofs=proofs,
    )

    assert not bundle.paper_proof_passes(
        BrokerCapability.MARKET_ORDER
    )


def test_wrong_sdk_version_is_rejected() -> None:
    with pytest.raises(IBKREvidenceError, match="SDK version"):
        IBKRPaperEvidenceBundle(
            provenance=_provenance(),
            captured_at=_CAPTURED,
            sdk_name="ib_async",
            sdk_version="2.0.0",
            real_provider_used=True,
            controlled_probe_passed=True,
            cleanup_passed=True,
            gates={"ci_quality_gate": "PASS"},
            proofs={},
        )


def test_provenance_requires_sha256() -> None:
    with pytest.raises(IBKREvidenceError, match="SHA-256"):
        IBKRPaperEvidenceProvenance(
            source_release="0.8.0b8",
            qualified_commit="abc123",
            artifact_name="artifact",
            artifact_json_sha256="not-a-sha",
        )


def test_bundle_round_trip_preserves_capability_proofs() -> None:
    bundle = _bundle()

    restored = IBKRPaperEvidenceBundle.from_dict(
        bundle.to_dict()
    )

    assert restored.to_dict() == bundle.to_dict()
    assert restored.provenance.source_ref == (
        "github-actions:ibkr:run:123:"
        "artifact-name:pytradekit-ibkr-paper-qualification"
    )
