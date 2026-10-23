"""Normalize a real IBKR PAPER adapter probe into retained C3 evidence."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ACL_DECLARED_CAPABILITIES,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    canonical_ibkr_evidence_sha256,
)
from pytradekit.brokers.compliance import BrokerCapability


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize sanitized real IBKR PAPER probe evidence, attach "
            "workflow provenance, and derive capability-specific C3 claims."
        )
    )
    parser.add_argument("--probe-report", type=Path, required=True)
    parser.add_argument("--qualified-commit", required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument(
        "--deterministic-ci-run-id",
        type=int,
        required=True,
    )
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.workflow_run_id <= 0:
        raise ValueError("--workflow-run-id must be positive.")
    if args.deterministic_ci_run_id <= 0:
        raise ValueError("--deterministic-ci-run-id must be positive.")
    if args.artifact_id <= 0:
        raise ValueError("--artifact-id must be positive.")

    _require_github_actions_provenance(
        qualified_commit=args.qualified_commit,
        workflow_run_id=args.workflow_run_id,
    )

    raw = json.loads(args.probe_report.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("IBKR PAPER probe root must be an object.")

    probe = {str(key): value for key, value in raw.items()}
    _validate_probe_identity(probe)

    raw_gates = _mapping(probe.get("gates"), "gates")
    raw_proofs = _mapping(probe.get("proofs"), "proofs")
    callback_counts = _mapping(
        probe.get("callback_counts"),
        "callback_counts",
    )

    gates = _normalize_gates(
        raw_gates=raw_gates,
        raw_proofs=raw_proofs,
        callback_counts=callback_counts,
        deterministic_ci_run_id=args.deterministic_ci_run_id,
    )
    proofs = _normalize_proofs(
        raw_proofs=raw_proofs,
        callback_counts=callback_counts,
    )

    controlled_probe_passed = _bool(
        probe.get("controlled_probe_passed"),
        "controlled_probe_passed",
    )
    cleanup_passed = _bool(
        probe.get("cleanup_passed"),
        "cleanup_passed",
    )
    release_ready = (
        controlled_probe_passed
        and cleanup_passed
        and gates["ci_quality_gate"] == "PASS"
        and _gate(raw_gates, "runbook_reviewed") == "PASS"
        and _bool(probe.get("real_provider_used"), "real_provider_used")
        and _bool(
            probe.get("economic_writes_requested"),
            "economic_writes_requested",
        )
    )

    provenance = IBKRPaperEvidenceProvenance(
        qualified_commit=_text(
            args.qualified_commit,
            "qualified_commit",
        ),
        artifact_name=_text(
            args.artifact_name,
            "artifact_name",
        ),
        artifact_json_sha256="0" * 64,
        source_ref=(
            "github-actions:ibkr-paper:"
            f"run:{args.workflow_run_id}:artifact:{args.artifact_id}"
        ),
        workflow_run_id=args.workflow_run_id,
        deterministic_ci_run_id=args.deterministic_ci_run_id,
        artifact_id=args.artifact_id,
    )

    sdk = _mapping(probe.get("sdk"), "sdk")
    captured_at = _utc_datetime(
        probe.get("captured_at"),
        "captured_at",
    )
    account_mask = _text(probe.get("account"), "account")

    unsigned = IBKRPaperEvidenceBundle(
        provenance=provenance,
        captured_at=captured_at,
        sdk_name=_text(sdk.get("name"), "sdk.name"),
        sdk_version=_text(sdk.get("version"), "sdk.version"),
        account_mask=account_mask,
        release_ready=release_ready,
        controlled_probe_passed=controlled_probe_passed,
        gates=gates,
        c3_capabilities=(),
        proofs=proofs,
    )
    c3_capabilities = tuple(
        capability
        for capability in IBKR_ACL_DECLARED_CAPABILITIES
        if unsigned.paper_proof_passes(capability)
    )

    payload = unsigned.to_dict()
    payload["c3_capabilities"] = [
        capability.value
        for capability in c3_capabilities
    ]
    raw_provenance = payload["provenance"]
    if not isinstance(raw_provenance, dict):
        raise RuntimeError("Normalized provenance unexpectedly changed type.")
    raw_provenance["artifact_json_sha256"] = (
        canonical_ibkr_evidence_sha256(payload)
    )

    evidence = IBKRPaperEvidenceBundle.from_dict(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            evidence.to_dict(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote normalized IBKR PAPER evidence to {args.output}")
    print(
        "C3 capabilities: "
        + ", ".join(
            capability.value
            for capability in evidence.c3_capabilities
        )
    )
    return 0


def _require_github_actions_provenance(
    *,
    qualified_commit: str,
    workflow_run_id: int,
) -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        raise ValueError(
            "C3 evidence normalization must run inside GitHub Actions."
        )
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    if github_sha != qualified_commit.strip():
        raise ValueError(
            "GITHUB_SHA does not match the qualified commit."
        )
    github_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if github_run_id != str(workflow_run_id):
        raise ValueError(
            "GITHUB_RUN_ID does not match --workflow-run-id."
        )
    workflow = os.environ.get("GITHUB_WORKFLOW", "").strip()
    if workflow != "IBKR Real PAPER Certification":
        raise ValueError(
            "Unexpected GitHub workflow for IBKR C3 evidence normalization."
        )


def _validate_probe_identity(probe: Mapping[str, object]) -> None:
    if _text(probe.get("schema_version"), "schema_version") != "probe-1":
        raise ValueError("Unsupported IBKR PAPER probe schema.")
    if _text(probe.get("provider"), "provider").lower() != "ibkr":
        raise ValueError("Probe provider must be ibkr.")
    if _text(probe.get("environment"), "environment").upper() != "PAPER":
        raise ValueError("Probe environment must be PAPER.")
    if _text(probe.get("release"), "release") != "0.8.0b8":
        raise ValueError("Probe release must be 0.8.0b8.")


def _normalize_gates(
    *,
    raw_gates: Mapping[str, object],
    raw_proofs: Mapping[str, object],
    callback_counts: Mapping[str, object],
    deterministic_ci_run_id: int,
) -> dict[str, str]:
    account = _proof(raw_proofs, BrokerCapability.ACCOUNT_QUERY)
    balance = _proof(raw_proofs, BrokerCapability.BALANCE_QUERY)
    market = _proof(raw_proofs, BrokerCapability.MARKET_ORDER)
    limit_order = _proof(raw_proofs, BrokerCapability.LIMIT_ORDER)
    cancel = _proof(raw_proofs, BrokerCapability.CANCEL_ORDER)
    client_ref = _proof(
        raw_proofs,
        BrokerCapability.CLIENT_ORDER_REFERENCE,
    )
    executions = _proof(
        raw_proofs,
        BrokerCapability.EXECUTION_FACTS,
    )
    position = _proof(
        raw_proofs,
        BrokerCapability.POSITION_QUERY,
    )

    callbacks_ok = (
        _gate(raw_gates, "real_paper_callbacks") == "PASS"
        and _int(callback_counts.get("open_order")) > 0
        and _int(callback_counts.get("order_status")) > 0
    )
    market_ok = (
        _int(market.get("submit_attempts")) == 1
        and _bool_default(market.get("filled"))
        and _bool_default(market.get("perm_id_present"))
        and _bool_default(market.get("exec_id_present"))
    )
    limit_ok = (
        _int(limit_order.get("submit_attempts")) == 1
        and _bool_default(limit_order.get("submitted"))
        and _bool_default(limit_order.get("limit_price_present"))
        and _bool_default(limit_order.get("market_rule_checked"))
    )
    cancel_ok = (
        _int(cancel.get("cancel_attempts")) == 1
        and _bool_default(cancel.get("requested"))
        and _bool_default(cancel.get("terminal_cancelled"))
    )
    identity_ok = (
        _int(client_ref.get("submit_attempts")) == 1
        and _bool_default(client_ref.get("round_trip_match"))
    )
    execution_ok = (
        _int(executions.get("exec_details_count")) >= 1
        and _bool_default(executions.get("exec_id_present"))
        and _int(callback_counts.get("exec_details")) > 0
    )
    account_snapshot_ok = (
        _gate(raw_gates, "real_paper_preflight") == "PASS"
        and _bool_default(account.get("account_ready"))
        and _bool_default(account.get("managed_account_match"))
        and _bool_default(balance.get("cash_present"))
        and _bool_default(balance.get("equity_present"))
        and _text_default(balance.get("currency")) == "USD"
    )

    return {
        "ci_quality_gate": (
            "PASS"
            if (
                deterministic_ci_run_id > 0
                and _gate(raw_gates, "ci_quality_gate") == "PASS"
            )
            else "FAIL"
        ),
        "paper_startup": (
            "PASS"
            if _gate(raw_gates, "real_paper_preflight") == "PASS"
            else "FAIL"
        ),
        "paper_account_snapshot": (
            "PASS" if account_snapshot_ok else "FAIL"
        ),
        "paper_order_callbacks": (
            "PASS" if callbacks_ok else "FAIL"
        ),
        "paper_market_order": "PASS" if market_ok else "FAIL",
        "paper_limit_order": "PASS" if limit_ok else "FAIL",
        "paper_cancel_order": "PASS" if cancel_ok else "FAIL",
        "paper_partial_fill": "PENDING",
        "paper_order_identity": (
            "PASS" if identity_ok else "FAIL"
        ),
        "paper_execution_details": (
            "PASS" if execution_ok else "FAIL"
        ),
        "paper_cleanup": (
            "PASS"
            if (
                _gate(raw_gates, "real_paper_cleanup") == "PASS"
                and _bool_default(position.get("baseline_restored"))
            )
            else "FAIL"
        ),
        "paper_reconnect_recovery": "PENDING",
    }


def _normalize_proofs(
    *,
    raw_proofs: Mapping[str, object],
    callback_counts: Mapping[str, object],
) -> dict[BrokerCapability, Mapping[str, object]]:
    account = _proof(raw_proofs, BrokerCapability.ACCOUNT_QUERY)
    order_query = _proof(raw_proofs, BrokerCapability.ORDER_QUERY)
    market = _proof(raw_proofs, BrokerCapability.MARKET_ORDER)
    limit_order = _proof(raw_proofs, BrokerCapability.LIMIT_ORDER)
    cancel = _proof(raw_proofs, BrokerCapability.CANCEL_ORDER)
    position = _proof(raw_proofs, BrokerCapability.POSITION_QUERY)
    balance = _proof(raw_proofs, BrokerCapability.BALANCE_QUERY)
    client_ref = _proof(
        raw_proofs,
        BrokerCapability.CLIENT_ORDER_REFERENCE,
    )
    executions = _proof(
        raw_proofs,
        BrokerCapability.EXECUTION_FACTS,
    )
    reconnect = _proof(
        raw_proofs,
        BrokerCapability.RECONNECT_RECOVERY,
    )

    return {
        BrokerCapability.ACCOUNT_QUERY: {
            "account_verified": _bool_default(
                account.get("managed_account_match")
            ),
            "account_ready": _bool_default(
                account.get("account_ready")
            ),
            "restrictions_explicit": False,
        },
        BrokerCapability.ORDER_QUERY: {
            "query_observed": _bool_default(
                order_query.get("query_observed")
            ),
            "perm_id_present": _bool_default(
                order_query.get("perm_id_present")
            ),
            "order_status_observed": _bool_default(
                order_query.get("status_observed")
            ),
        },
        BrokerCapability.MARKET_ORDER: {
            "submit_attempts": _int(market.get("submit_attempts")),
            "perm_id_present": _bool_default(
                market.get("perm_id_present")
            ),
            "terminal_status": (
                "Filled"
                if _bool_default(market.get("filled"))
                else ""
            ),
            "exec_id_present": _bool_default(
                market.get("exec_id_present")
            ),
        },
        BrokerCapability.LIMIT_ORDER: {
            "submit_attempts": _int(
                limit_order.get("submit_attempts")
            ),
            "accepted": _bool_default(
                limit_order.get("submitted")
            ),
            "limit_price_present": _bool_default(
                limit_order.get("limit_price_present")
            ),
            "price_rule_validated": _bool_default(
                limit_order.get("market_rule_checked")
            ),
        },
        BrokerCapability.CANCEL_ORDER: {
            "cancel_attempts": _int(cancel.get("cancel_attempts")),
            "requested": _bool_default(cancel.get("requested")),
            "final_status": (
                "Cancelled"
                if _bool_default(cancel.get("terminal_cancelled"))
                else ""
            ),
        },
        BrokerCapability.PARTIAL_FILL: {
            "partial_fill_observed": False,
            "partial_exec_count": 0,
            "distinct_exec_ids": False,
        },
        BrokerCapability.POSITION_QUERY: {
            "position_query_observed": _bool_default(
                position.get("baseline_observed")
            ),
            "baseline_restored": _bool_default(
                position.get("baseline_restored")
            ),
        },
        BrokerCapability.BALANCE_QUERY: {
            "cash_present": _bool_default(
                balance.get("cash_present")
            ),
            "equity_present": _bool_default(
                balance.get("equity_present")
            ),
            "currency": _text_default(balance.get("currency")),
        },
        BrokerCapability.CLIENT_ORDER_REFERENCE: {
            "order_ref_round_trip": _bool_default(
                client_ref.get("round_trip_match")
            ),
            "submit_attempts": _int(
                client_ref.get("submit_attempts")
            ),
            "resubmitted": False,
        },
        BrokerCapability.EXECUTION_FACTS: {
            "exec_details_count": _int(
                executions.get("exec_details_count")
            ),
            "exec_ids_present": _bool_default(
                executions.get("exec_id_present")
            ),
            "fill_mapping_observed": False,
        },
        BrokerCapability.RECONNECT_RECOVERY: {
            "reconnect_cycles": (
                1
                if _bool_default(reconnect.get("reconnect_observed"))
                else 0
            ),
            "fresh_reconciliation": False,
            "no_economic_replay": (
                not _bool_default(reconnect.get("economic_replay"))
            ),
            "write_readmission_observed": False,
        },
    }


def _proof(
    proofs: Mapping[str, object],
    capability: BrokerCapability,
) -> Mapping[str, object]:
    value = proofs.get(capability.value)
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _mapping(
    value: object,
    field_name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object.")
    return {str(key): item for key, item in value.items()}


def _gate(
    gates: Mapping[str, object],
    name: str,
) -> str:
    value = gates.get(name)
    return value.strip().upper() if isinstance(value, str) else ""


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


def _text_default(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be a bool.")
    return value


def _bool_default(value: object) -> bool:
    return value is True


def _int(value: object) -> int:
    return value if type(value) is int else 0


def _utc_datetime(value: object, field_name: str) -> datetime:
    text = _text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO-8601 datetime."
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"{field_name} must include a timezone."
        )
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
