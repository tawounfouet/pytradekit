"""Normalize a real IBKR PAPER probe into retained compliance evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

from pytradekit.brokers.adapters.ibkr import (
    IBKRPaperEvidenceBundle,
    IBKRPaperEvidenceProvenance,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Attach immutable provenance and SHA-256 to one sanitized "
            "IBKR PAPER probe report."
        )
    )
    parser.add_argument("--probe-report", type=Path, required=True)
    parser.add_argument("--source-release", required=True)
    parser.add_argument("--qualified-commit", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--workflow-run-id", type=int)
    parser.add_argument("--deterministic-ci-run-id", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    raw = args.probe_report.read_bytes()
    payload = cast(
        dict[str, object],
        json.loads(raw.decode("utf-8")),
    )
    provenance = IBKRPaperEvidenceProvenance(
        source_release=args.source_release,
        qualified_commit=args.qualified_commit,
        artifact_name=args.artifact_name,
        artifact_json_sha256=hashlib.sha256(raw).hexdigest(),
        workflow_run_id=args.workflow_run_id,
        deterministic_ci_run_id=args.deterministic_ci_run_id,
    )
    evidence = IBKRPaperEvidenceBundle.from_probe_report(
        payload,
        provenance=provenance,
    )
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
    print(f"probe_sha256={provenance.artifact_json_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
