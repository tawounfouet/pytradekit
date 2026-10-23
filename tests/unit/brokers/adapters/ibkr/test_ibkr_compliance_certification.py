"""Unit tests for IBKR LOT-06.7 compliance certification."""

from datetime import UTC, datetime

from pytradekit.brokers.adapters.ibkr import (
    IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    build_ibkr_certification_manifest,
    build_ibkr_certification_run,
    expected_ibkr_certification_levels,
)
from pytradekit.brokers.compliance import (
    BrokerCapability,
    CertificationLevel,
)

_CAPTURED = datetime(2026, 10, 23, 12, 5, tzinfo=UTC)


def _bundle(
    *,
    market_exec_id: bool = True,
    real_provider_used: bool = True,
) -> IBKRPaperEvidenceBundle:
    proofs: dict[BrokerCapability, dict[str, object]] = {
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
            "exec_id_present": market_exec_id,
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
    return IBKRPaperEvidenceBundle(
        provenance=IBKRPaperEvidenceProvenance(
            source_release="0.8.0b8",
            qualified_commit="qualified-commit",
            artifact_name="ibkr-paper",
            artifact_json_sha256="b" * 64,
            workflow_run_id=456,
        ),
        captured_at=_CAPTURED,
        sdk_name="ib_async",
        sdk_version="2.1.0",
        real_provider_used=real_provider_used,
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


def test_certification_manifest_is_runtime_backed_and_paper_only() -> None:
    manifest = build_ibkr_certification_manifest()

    assert manifest.provider == "ibkr"
    assert manifest.environment.value == "PAPER"
    assert manifest.sdk_name == "ib_async"
    assert manifest.sdk_version == "2.1.0"
    assert not manifest.supports(BrokerCapability.LATEST_QUOTE)
    assert not manifest.supports(BrokerCapability.REPLACE_ORDER)


def test_full_retained_evidence_promotes_eligible_capabilities_to_c3() -> None:
    evidence = _bundle()

    run = build_ibkr_certification_run(evidence)
    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }

    for capability in IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES:
        assert (
            observed[capability]
            is CertificationLevel.C3_PAPER_QUALIFIED
        )
    assert (
        observed[BrokerCapability.PARTIAL_FILL]
        is CertificationLevel.C2_INTEGRATION_QUALIFIED
    )


def test_incomplete_real_proof_stays_c2_without_overclaim() -> None:
    evidence = _bundle(market_exec_id=False)

    run = build_ibkr_certification_run(evidence)
    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }

    assert (
        observed[BrokerCapability.MARKET_ORDER]
        is CertificationLevel.C2_INTEGRATION_QUALIFIED
    )
    assert not run.report.complete


def test_non_provider_evidence_cannot_promote_any_capability() -> None:
    evidence = _bundle(real_provider_used=False)

    expected = expected_ibkr_certification_levels(evidence)

    assert all(
        level is CertificationLevel.C2_INTEGRATION_QUALIFIED
        for level in expected.values()
    )
