"""Architecture fitness functions for LOT-07 safety integration."""

from pathlib import Path

SUBMIT = Path("src/pytradekit/orders/application/submit_order.py")
READINESS = Path("src/pytradekit/runtime/trading_readiness.py")
RECONCILE = Path("src/pytradekit/reconciliation/application/reconcile_account.py")
RECOVERY = Path("src/pytradekit/reconciliation/adapters/postgres/recovery.py")
STRATEGY = Path("src/pytradekit/strategy/application/runtime.py")


def test_ff_031_risk_increasing_submit_consumes_consistency_gate() -> None:
    source = SUBMIT.read_text(encoding="utf-8")
    assert "ensure_risk_increase_allowed" in source


def test_ff_032_readiness_consumes_reconciliation_result() -> None:
    source = READINESS.read_text(encoding="utf-8")
    assert "ConsistencyStatus.CONSISTENT" in source
    assert "StateConfidence.HIGH" in source


def test_ff_033_recovery_uses_canonical_business_path_not_direct_orm_mutation() -> None:
    source = RECOVERY.read_text(encoding="utf-8")
    assert "ProcessFill" in source
    assert "ApplyFillToPortfolio" in source
    assert "PostgresUnitOfWork" in source
    assert "Model" not in source


def test_ff_034_strategy_runtime_consumes_consistency_admission() -> None:
    source = STRATEGY.read_text(encoding="utf-8")
    assert "StrategyAdmissionPort" in source
    assert "allow_new_targets" in source


def test_ff_035_stale_reconciliation_is_checked_before_resolution_side_effect() -> None:
    source = RECONCILE.read_text(encoding="utf-8")
    watermark_check = source.index("_same_economic_cut")
    executor_apply = source.index("self._executor.apply")
    assert watermark_check < executor_apply
