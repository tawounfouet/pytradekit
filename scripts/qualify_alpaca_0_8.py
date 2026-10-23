"""Qualify the frozen Alpaca PAPER adapter through the PyTradeKit 0.8 compliance model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from pytradekit.brokers.adapters.alpaca.compliance import (
    ALPACA_EXPECTED_CERTIFICATION_LEVELS,
    build_alpaca_certification_run,
)
from pytradekit.brokers.adapters.alpaca.compliance_evidence import (
    AlpacaPaperEvidenceBundle,
    AlpacaPaperEvidenceProvenance,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay retained Alpaca PAPER evidence through the PyTradeKit 0.8 "
            "broker compliance harness. This command has no LIVE mode."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--evidence-record",
        type=Path,
        help="Normalized retained Alpaca PAPER evidence record.",
    )
    source.add_argument(
        "--v050-report",
        type=Path,
        help="Sanitized v0.5-style real Alpaca PAPER qualification report.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Generated 0.8 ComplianceRun JSON output.",
    )
    parser.add_argument(
        "--normalized-output",
        type=Path,
        help="Optional normalized evidence output when --v050-report is used.",
    )
    parser.add_argument(
        "--qualified-commit",
        help="Exact commit exercised by the real PAPER report.",
    )
    parser.add_argument(
        "--source-release",
        default="v0.8.0a3",
        help="Release identifier associated with --v050-report.",
    )
    parser.add_argument(
        "--release-commit",
        help="Optional release commit linked to --v050-report.",
    )
    parser.add_argument(
        "--deterministic-ci-run-id",
        type=int,
        help="Optional deterministic CI run ID linked to the evidence.",
    )
    parser.add_argument(
        "--workflow-run-id",
        type=int,
        help="Optional real PAPER GitHub Actions run ID.",
    )
    parser.add_argument(
        "--artifact-id",
        type=int,
        help="Optional GitHub Actions artifact ID.",
    )
    parser.add_argument(
        "--artifact-name",
        default="pytradekit-v080-alpaca-paper-certification",
        help="Source artifact name.",
    )
    parser.add_argument(
        "--artifact-zip-sha256",
        help="Optional SHA-256 digest of the uploaded source artifact ZIP.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    try:
        bundle = _load_bundle(args)
        run = build_alpaca_certification_run(bundle)
    except Exception as exc:
        print(
            f"Alpaca 0.8 compliance qualification failed ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(run.to_json() + "\n", encoding="utf-8")

    print("PyTradeKit 0.8 Alpaca compliance certification: PASS")
    print(f"provider: {run.report.provider}")
    print(f"environment: {run.report.environment.value}")
    print(f"qualified commit: {run.report.commit_sha}")
    for capability, expected_level in ALPACA_EXPECTED_CERTIFICATION_LEVELS.items():
        actual = next(
            item.certification_level
            for item in run.report.capability_results
            if item.capability is capability
        )
        print(f"{capability.value}: {actual.code}")
        if actual is not expected_level:
            return 1
    print(f"evidence records: {len(run.evidence)}")
    print(f"output: {args.output}")
    return 0


def _load_bundle(args: argparse.Namespace) -> AlpacaPaperEvidenceBundle:
    evidence_record = cast(Path | None, args.evidence_record)
    if evidence_record is not None:
        return AlpacaPaperEvidenceBundle.from_dict(_load_mapping(evidence_record))

    report_path = cast(Path, args.v050_report)
    qualified_commit = cast(str | None, args.qualified_commit)
    if qualified_commit is None or not qualified_commit.strip():
        raise ValueError("--qualified-commit is required with --v050-report.")

    raw_bytes = report_path.read_bytes()
    report = _mapping_from_json_bytes(raw_bytes)
    provenance = AlpacaPaperEvidenceProvenance(
        source_release=cast(str, args.source_release),
        qualified_commit=qualified_commit,
        release_commit=cast(str | None, args.release_commit),
        deterministic_ci_run_id=cast(int | None, args.deterministic_ci_run_id),
        workflow_run_id=cast(int | None, args.workflow_run_id),
        artifact_id=cast(int | None, args.artifact_id),
        artifact_name=cast(str, args.artifact_name),
        artifact_zip_sha256=cast(str | None, args.artifact_zip_sha256),
        artifact_json_sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )
    bundle = AlpacaPaperEvidenceBundle.from_v050_report(
        report,
        provenance=provenance,
    )

    normalized_output = cast(Path | None, args.normalized_output)
    if normalized_output is not None:
        normalized_output.parent.mkdir(parents=True, exist_ok=True)
        normalized_output.write_text(
            json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return bundle


def _load_mapping(path: Path) -> Mapping[str, object]:
    return _mapping_from_json_bytes(path.read_bytes())


def _mapping_from_json_bytes(raw_bytes: bytes) -> Mapping[str, object]:
    raw: object = json.loads(raw_bytes)
    if not isinstance(raw, dict):
        raise ValueError("Qualification JSON root must be an object.")
    result: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError("Qualification JSON keys must be strings.")
        result[key] = value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
