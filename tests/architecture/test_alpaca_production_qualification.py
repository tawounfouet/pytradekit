"""Architecture fitness functions for LOT-10 production qualification."""

from pathlib import Path

OPERATIONS = Path("src/pytradekit/runtime/operations.py")
FAULTS = Path("src/pytradekit/runtime/faults.py")
QUALIFICATION = Path("src/pytradekit/runtime/qualification.py")
STREAM = Path("src/pytradekit/brokers/adapters/alpaca/stream.py")
REAL_HARNESS = Path("scripts/alpaca_paper_v050_qualification.py")


def test_fault_injection_is_named_and_has_no_random_behavior() -> None:
    source = FAULTS.read_text(encoding="utf-8")

    assert "FaultPoint" in source
    assert "OneShotFaultInjector" in source
    assert "random" not in source.lower()


def test_trade_update_pipeline_exposes_before_and_after_commit_crash_windows() -> None:
    source = STREAM.read_text(encoding="utf-8")

    assert "FaultPoint.BEFORE_COMMIT" in source
    assert "uow.commit()" in source
    assert "FaultPoint.AFTER_COMMIT" in source
    assert source.index("FaultPoint.BEFORE_COMMIT") < source.index("uow.commit()")
    assert source.index("uow.commit()") < source.index("FaultPoint.AFTER_COMMIT")


def test_operational_shell_blocks_submit_until_readiness() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")

    assert "RuntimeLifecycleState.READY" in source
    assert "submission_slot" in source
    assert "begin_draining" in source
    assert "wait_for_submissions" in source


def test_shutdown_keeps_cancel_path_available_while_draining() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")

    assert "RuntimeLifecycleState.DRAINING" in source
    assert "ensure_cancel_allowed" in source


def test_release_gate_requires_real_paper_evidence() -> None:
    source = QUALIFICATION.read_text(encoding="utf-8")

    required = (
        "real_paper_runtime_start_restart",
        "real_paper_market_limit_cancel",
        "real_paper_trade_updates",
        "real_paper_uncertain_recovery",
        "real_paper_cleanup",
    )
    assert all(name in source for name in required)


def test_real_qualification_harness_has_no_live_mode() -> None:
    source = REAL_HARNESS.read_text(encoding="utf-8")

    assert "PAPER" in source
    assert "LIVE" not in source
    assert "paper=False" not in source


def test_real_order_writes_require_explicit_opt_in() -> None:
    source = REAL_HARNESS.read_text(encoding="utf-8")

    assert "--with-orders" in source
    assert "AlpacaPaperOrderProbeConfig.from_environment" in source
