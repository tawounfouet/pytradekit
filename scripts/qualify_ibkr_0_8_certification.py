"""Replay retained IBKR PAPER evidence through the 0.8 compliance harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from pytradekit.brokers.compliance import (
    BrokerCapability,
    CertificationLevel,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES,
    IBKRPaperEvidenceBundle,
    build_ibkr_certification_run,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the IBKR compliance report from one retained "
            "sanitized PAPER evidence record."
        )
    )
    parser.add_argument(
        "--evidence-record",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--require-c3-target",
        action="store_true",
        help=(
            "Fail unless every LOT-06.7 C3-eligible capability reaches "
            "C3_PAPER_QUALIFIED."
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    payload = cast(
        dict[str, object],
        json.loads(
            args.evidence_record.read_text(encoding="utf-8")
        ),
    )
    evidence = IBKRPaperEvidenceBundle.from_dict(payload)
    run = build_ibkr_certification_run(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            run.to_dict(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    levels = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }
    c3 = sorted(
        capability.value
        for capability, level in levels.items()
        if level is CertificationLevel.C3_PAPER_QUALIFIED
    )
    print(f"Wrote IBKR compliance report to {args.output}")
    print("C3 capabilities: " + (", ".join(c3) if c3 else "none"))

    if args.require_c3_target:
        missing = sorted(
            capability.value
            for capability in IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES
            if levels.get(capability)
            is not CertificationLevel.C3_PAPER_QUALIFIED
        )
        if missing:
            print(
                "Missing required C3 PAPER capabilities: "
                + ", ".join(missing)
            )
            return 1

    partial = levels.get(BrokerCapability.PARTIAL_FILL)
    if partial is not CertificationLevel.C2_INTEGRATION_QUALIFIED:
        print("PARTIAL_FILL must remain C2 without real partial-fill proof.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
