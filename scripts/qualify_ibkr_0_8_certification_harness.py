"""Qualify the IBKR LOT-06.7 certification harness without provider use."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pytradekit.brokers.compliance import CertificationLevel
from pytradekit.brokers.adapters.ibkr import (
    IBKR_BASELINE_CERTIFICATION_LEVELS,
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
    build_ibkr_certification_run,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prove that deterministic CI cannot manufacture IBKR C3 "
            "PAPER certification."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    evidence = IBKRPaperEvidenceBundle(
        provenance=IBKRPaperEvidenceProvenance(
            source_release="0.8.0b8",
            qualified_commit="deterministic-ci",
            artifact_name="no-real-provider-artifact",
            artifact_json_sha256="d" * 64,
        ),
        captured_at=datetime(2026, 10, 23, 12, 10, tzinfo=UTC),
        sdk_name="ib_async",
        sdk_version="2.1.0",
        real_provider_used=False,
        controlled_probe_passed=False,
        cleanup_passed=False,
        gates={"ci_quality_gate": "PASS"},
        proofs={},
    )
    run = build_ibkr_certification_run(evidence)
    levels = {
        item.capability.value: item.certification_level.code
        for item in run.report.capability_results
    }
    expected = {
        capability.value: level.code
        for capability, level
        in IBKR_BASELINE_CERTIFICATION_LEVELS.items()
    }
    if levels != expected:
        raise RuntimeError(
            "Deterministic IBKR certification exceeded the C2 baseline."
        )
    if any(
        item.certification_level
        is CertificationLevel.C3_PAPER_QUALIFIED
        for item in run.report.capability_results
    ):
        raise RuntimeError(
            "Deterministic CI manufactured an IBKR C3 capability."
        )

    payload = {
        "lot": "LOT-06.7",
        "release": "0.8.0b8",
        "provider": "ibkr",
        "environment": "PAPER",
        "real_provider_used": False,
        "retained_paper_evidence_present": False,
        "c3_claimed": False,
        "baseline_levels": levels,
        "real_paper_workflow_required": True,
        "live_available": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("PyTradeKit 0.8 LOT-06.7 certification harness: PASS")
    print("real provider used: false")
    print("C3 claimed: false")
    print("manual PAPER workflow required: true")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
