"""Architecture fitness functions for the controlled IBKR PAPER probe."""

from pathlib import Path

_PROBE = Path("scripts/ibkr_paper_controlled_probe.py")
_CI = Path(".github/workflows/ci.yml")
_REAL_WORKFLOW = Path(".github/workflows/ibkr-real-paper.yml")
_NORMALIZER = Path("scripts/normalize_ibkr_paper_evidence.py")


def test_controlled_probe_is_paper_only_and_explicitly_acknowledged() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert "I_UNDERSTAND_IBKR_PAPER_ORDERS_WILL_BE_CREATED" in source
    assert "4001" not in source
    assert "7496" not in source
    assert "reqGlobalCancel" not in source


def test_controlled_probe_uses_canonical_execution_adapter() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert "build_ibkr_execution_adapter" in source
    assert "execution.submit(" in source
    assert "execution.cancel(" in source
    assert ".placeOrder(" not in source
    assert ".cancelOrder(" not in source


def test_standard_ci_never_runs_real_paper_probe() -> None:
    source = _CI.read_text(encoding="utf-8")

    assert "ibkr_paper_controlled_probe.py" not in source



def test_real_paper_workflow_verifies_ci_and_normalizes_evidence() -> None:
    source = _REAL_WORKFLOW.read_text(encoding="utf-8")

    assert "deterministic_ci_run_id" in source
    assert "github.rest.actions.getWorkflowRun" in source
    assert "run.head_sha !== context.sha" in source
    assert 'run.conclusion !== "success"' in source
    assert "normalize_ibkr_paper_evidence.py" in source
    assert "real-paper-probe.json" in source
    assert "real-paper-evidence.json" in source


def test_evidence_normalizer_derives_c3_from_contract() -> None:
    source = _NORMALIZER.read_text(encoding="utf-8")

    assert "paper_proof_passes" in source
    assert "canonical_ibkr_evidence_sha256" in source
    assert "deterministic_ci_run_id" in source
    assert "fill_mapping_observed" in source
    assert '"fresh_reconciliation": False' in source
