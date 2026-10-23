"""Qualify PyTradeKit 0.8 LOT-06.7 IBKR compliance certification."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pytradekit.brokers.adapters.ibkr import (
    IBKRPaperEvidenceBundle,
    build_ibkr_certification_run,
)
from pytradekit.brokers.compliance import CertificationLevel


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic IBKR compliance certification and optionally "
            "replay retained real PAPER evidence."
        )
    )
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--paper-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    commit_sha = args.commit_sha.strip()
    if not commit_sha:
        raise ValueError("--commit-sha must be non-empty.")

    evidence: IBKRPaperEvidenceBundle | None = None
    captured_at = datetime(2026, 10, 23, 13, 0, tzinfo=UTC)

    if args.paper_evidence is not None:
        raw = json.loads(
            args.paper_evidence.read_text(encoding="utf-8")
        )
        if not isinstance(raw, dict):
            raise ValueError("PAPER evidence JSON root must be an object.")
        evidence = IBKRPaperEvidenceBundle.from_dict(
            cast(dict[str, object], raw)
        )
        captured_at = evidence.captured_at

    run = build_ibkr_certification_run(
        commit_sha=commit_sha,
        captured_at=captured_at,
        evidence=evidence,
    )
    levels = {
        item.capability.value: item.certification_level.code
        for item in run.report.capability_results
    }
    c3 = sorted(
        capability
        for capability, level in levels.items()
        if level == CertificationLevel.C3_PAPER_QUALIFIED.code
    )

    if evidence is None and c3:
        raise RuntimeError(
            "Deterministic certification must not emit C3 without PAPER evidence."
        )

    payload = {
        "lot": "LOT-06.7",
        "release": "0.8.0b8",
        "provider": "ibkr",
        "environment": "PAPER",
        "real_paper_evidence_used": evidence is not None,
        "c3_capabilities": c3,
        "certification_levels": levels,
        "report_complete": run.report.complete,
        "compliance_run": run.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PyTradeKit 0.8 LOT-06.7 IBKR compliance certification: PASS")
    print(f"real PAPER evidence used: {str(evidence is not None).lower()}")
    print(f"C3 capability count: {len(c3)}")
    print(f"report complete: {str(run.report.complete).lower()}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
