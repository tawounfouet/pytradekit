"""Architecture fitness functions for the controlled IBKR PAPER probe."""

from pathlib import Path

_PROBE = Path("scripts/ibkr_paper_controlled_probe.py")
_CI = Path(".github/workflows/ci.yml")


def test_controlled_probe_is_paper_only_and_explicitly_acknowledged() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert "I_UNDERSTAND_IBKR_PAPER_ORDERS_WILL_BE_CREATED" in source
    assert "4001" not in source
    assert "7496" not in source
    assert "reqGlobalCancel" not in source


def test_controlled_probe_has_single_provider_write_call_sites() -> None:
    source = _PROBE.read_text(encoding="utf-8")

    assert source.count("client.placeOrder(") == 1
    assert source.count("client.cancelOrder(") == 1


def test_standard_ci_never_runs_real_paper_probe() -> None:
    source = _CI.read_text(encoding="utf-8")

    assert "ibkr_paper_controlled_probe.py" not in source
