"""Unit qualification for Alpaca LOT-03 capability certification."""

import json
from collections.abc import Mapping
from pathlib import Path

from pytradekit.brokers.adapters.alpaca.compliance import (
    ALPACA_DECLARED_CAPABILITIES,
    ALPACA_EXPECTED_CERTIFICATION_LEVELS,
    ALPACA_REAL_PAPER_C3_CAPABILITIES,
    build_alpaca_capability_manifest,
    build_alpaca_certification_run,
    build_alpaca_compliance_requirements,
    build_alpaca_compliance_scenarios,
)
from pytradekit.brokers.adapters.alpaca.compliance_evidence import (
    AlpacaPaperEvidenceBundle,
)
from pytradekit.brokers.compliance import (
    BrokerCapability,
    CertificationLevel,
    ComplianceEvidenceType,
)
from pytradekit.runtime import RuntimeEnvironment

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


def test_alpaca_manifest_maps_frozen_paper_scope_without_replace() -> None:
    manifest = build_alpaca_capability_manifest()

    assert manifest.provider == "alpaca"
    assert manifest.environment is RuntimeEnvironment.PAPER
    assert manifest.sdk_name == "alpaca-py"
    assert manifest.sdk_version == "0.44.0"
    assert manifest.capability_set == frozenset(ALPACA_DECLARED_CAPABILITIES)
    assert not manifest.supports(BrokerCapability.REPLACE_ORDER)


def test_requirements_keep_partial_fill_at_c2_and_real_proofs_at_c3() -> None:
    requirements = build_alpaca_compliance_requirements()

    partial = tuple(
        item
        for item in requirements
        if item.capability is BrokerCapability.PARTIAL_FILL
    )
    assert tuple(item.level for item in partial) == (
        CertificationLevel.C2_INTEGRATION_QUALIFIED,
    )
    assert partial[0].evidence_type is ComplianceEvidenceType.INTEGRATION

    for capability in ALPACA_REAL_PAPER_C3_CAPABILITIES:
        levels = {
            item.level
            for item in requirements
            if item.capability is capability
        }
        assert levels == {
            CertificationLevel.C2_INTEGRATION_QUALIFIED,
            CertificationLevel.C3_PAPER_QUALIFIED,
        }


def test_scenario_suite_has_one_c2_for_every_capability_and_c3_only_when_proven() -> None:
    scenarios = build_alpaca_compliance_scenarios()

    c2 = tuple(
        scenario
        for scenario in scenarios
        if scenario.required_evidence == (ComplianceEvidenceType.INTEGRATION,)
    )
    c3 = tuple(
        scenario
        for scenario in scenarios
        if scenario.required_evidence == (ComplianceEvidenceType.PAPER,)
    )

    assert len(c2) == len(ALPACA_DECLARED_CAPABILITIES)
    assert {scenario.capability for scenario in c3} == set(
        ALPACA_REAL_PAPER_C3_CAPABILITIES
    )


def test_retained_real_paper_evidence_produces_expected_certification_matrix() -> None:
    run = build_alpaca_certification_run(_bundle())
    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }

    assert observed == dict(ALPACA_EXPECTED_CERTIFICATION_LEVELS)
    assert run.report.complete
    assert observed[BrokerCapability.PARTIAL_FILL] is (
        CertificationLevel.C2_INTEGRATION_QUALIFIED
    )
    assert all(
        observed[capability] is CertificationLevel.C3_PAPER_QUALIFIED
        for capability in ALPACA_REAL_PAPER_C3_CAPABILITIES
    )
