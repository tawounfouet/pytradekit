"""Architecture fitness functions for Alpaca LOT-03 certification."""

from pathlib import Path

_ALPACA_COMPLIANCE = Path(
    "src/pytradekit/brokers/adapters/alpaca/compliance.py"
)
_ALPACA_EVIDENCE = Path(
    "docs/qualification/evidence/alpaca/v050-paper-20261022.json"
)
_REAL_WORKFLOW = Path(
    ".github/workflows/v080-alpaca-paper-certification.yml"
)


def test_alpaca_compliance_stays_inside_provider_adapter_boundary() -> None:
    source = _ALPACA_COMPLIANCE.read_text(encoding="utf-8")

    assert "pytradekit.brokers.adapters.ibkr" not in source
    assert "paper=False" not in source
    assert "RuntimeEnvironment.LIVE" not in source


def test_retained_alpaca_evidence_is_secret_safe_and_paper_only() -> None:
    source = _ALPACA_EVIDENCE.read_text(encoding="utf-8")
    lowered = source.lower()

    assert '"environment": "PAPER"' in source
    assert "api_key" not in lowered
    assert "secret_key" not in lowered
    assert "password" not in lowered
    assert "bearer " not in lowered


def test_real_alpaca_080_workflow_has_no_live_mode() -> None:
    source = _REAL_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch" in source
    assert "PYTRADEKIT_RUNTIME_ENVIRONMENT: PAPER" in source
    assert "paper=False" not in source
    assert "LIVE" not in source
