"""LOT-03 qualification against retained real Alpaca PAPER evidence."""

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from pytradekit.brokers.adapters.alpaca.compliance import (
    ALPACA_COMPLIANCE_ADAPTER_VERSION,
    ALPACA_EXPECTED_CERTIFICATION_LEVELS,
    build_alpaca_capability_manifest,
    build_alpaca_certification_run,
)
from pytradekit.brokers.adapters.alpaca.compliance_evidence import (
    AlpacaPaperEvidenceBundle,
)
from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
    BrokerCapability,
    CertificationLevel,
    StaleEvidencePolicy,
)

_EVIDENCE = Path(
    "docs/qualification/evidence/alpaca/v050-paper-20261022.json"
)


def _bundle() -> AlpacaPaperEvidenceBundle:
    raw: object = json.loads(_EVIDENCE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    record: Mapping[str, object] = {
        str(key): value
        for key, value in raw.items()
    }
    return AlpacaPaperEvidenceBundle.from_dict(record)


def test_lot03_replays_real_paper_evidence_through_common_compliance_harness() -> None:
    bundle = _bundle()
    run = build_alpaca_certification_run(bundle)

    assert run.report.provider == "alpaca"
    assert run.report.adapter_version == ALPACA_COMPLIANCE_ADAPTER_VERSION
    assert run.report.commit_sha == bundle.provenance.qualified_commit
    assert run.report.complete
    assert len(run.evidence) == 23
    assert len(run.registry.entries) == len(ALPACA_EXPECTED_CERTIFICATION_LEVELS)

    for capability, expected in ALPACA_EXPECTED_CERTIFICATION_LEVELS.items():
        record = next(
            item
            for item in run.registry.entries
            if item.capability is capability
        )
        assert record.certification_level is expected


def test_lot03_c3_evidence_points_back_to_real_github_actions_provenance() -> None:
    run = build_alpaca_certification_run(_bundle())

    paper_evidence = tuple(
        item
        for item in run.evidence
        if item.evidence_type.value == "PAPER"
    )
    assert paper_evidence

    for item in paper_evidence:
        source = item.payload["source"]
        assert isinstance(source, dict)
        assert source["workflow_run_id"] == 39789766678
        assert source["artifact_id"] == 12430172671
        assert source["source_release"] == "v0.5.0"


def test_lot03_partial_fill_remains_c2_without_real_partial_fill_event() -> None:
    run = build_alpaca_certification_run(_bundle())
    partial = next(
        item
        for item in run.registry.entries
        if item.capability is BrokerCapability.PARTIAL_FILL
    )

    assert partial.certification_level is CertificationLevel.C2_INTEGRATION_QUALIFIED


def test_lot03_stale_adapter_version_invalidates_retained_certification() -> None:
    run = build_alpaca_certification_run(_bundle())
    manifest = build_alpaca_capability_manifest()
    changed_manifest = replace(
        manifest,
        adapter_version="0.5.1-changed",
    )

    current = run.registry.find_current(
        provider="alpaca",
        environment=manifest.environment,
        capability=BrokerCapability.MARKET_ORDER,
        contract_version=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION,
        manifest=changed_manifest,
        evidence_by_ref=run.evidence_by_ref,
        stale_policy=StaleEvidencePolicy(),
        now=datetime(2026, 10, 23, 0, 30, tzinfo=UTC),
    )

    assert current is None
