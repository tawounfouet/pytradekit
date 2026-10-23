"""Architecture fitness functions for IBKR LOT-06.7 certification."""

from pathlib import Path

_COMPLIANCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/compliance.py"
)
_EVIDENCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/paper_evidence.py"
)


def test_c3_requires_retained_paper_evidence() -> None:
    source = _COMPLIANCE.read_text(encoding="utf-8")

    assert "C3_PAPER_QUALIFIED" in source
    assert "evidence.c3_capabilities" in source
    assert "evidence.paper_proof_passes" in source


def test_no_default_c3_capability_set_exists() -> None:
    source = _COMPLIANCE.read_text(encoding="utf-8")

    assert "IBKR_REAL_PAPER_C3_CAPABILITIES" not in source
    assert "C3_PAPER_QUALIFIED" not in source.split(
        "IBKR_BASELINE_CERTIFICATION_LEVELS",
        maxsplit=1,
    )[1].split(")", maxsplit=1)[0]


def test_retained_evidence_is_commit_and_sdk_linked() -> None:
    source = _EVIDENCE.read_text(encoding="utf-8")

    assert "qualified_commit" in source
    assert "artifact_json_sha256" in source
    assert "IBKR_ASYNC_VERSION_TARGET" in source
    assert "c3_capabilities" in source


def test_paper_evidence_model_has_no_provider_network_call() -> None:
    source = _EVIDENCE.read_text(encoding="utf-8")

    assert "placeOrder(" not in source
    assert "cancelOrder(" not in source
    assert "reqMarketRule(" not in source


def test_certification_replay_has_no_economic_write_call() -> None:
    source = _COMPLIANCE.read_text(encoding="utf-8")

    assert ".placeOrder(" not in source
    assert ".cancelOrder(" not in source
