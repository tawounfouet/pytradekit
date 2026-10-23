"""Architecture fitness functions for IBKR LOT-06.2 read-side reconciliation."""

from pathlib import Path

_READ_SIDE = Path("src/pytradekit/brokers/adapters/ibkr/read_side.py")
_STARTUP = Path(
    "src/pytradekit/brokers/adapters/ibkr/startup_reconciliation.py"
)
_CANONICAL_ROOTS = (
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation/domain"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_read_side_contains_no_economic_write_method() -> None:
    source = _READ_SIDE.read_text(encoding="utf-8")

    assert ".placeOrder(" not in source
    assert ".cancelOrder(" not in source
    assert "place_order" not in source
    assert "cancel_order" not in source


def test_read_side_uses_synchronized_session_state() -> None:
    source = _READ_SIDE.read_text(encoding="utf-8")

    assert "accountValues(" in source
    assert "portfolio(" in source
    assert "trades(" in source
    assert "fills(" in source
    assert "isConnected()" in source


def test_read_side_reuses_lot05_semantics() -> None:
    source = _READ_SIDE.read_text(encoding="utf-8")

    assert "map_ibkr_account_snapshot" in source
    assert "map_ibkr_position_snapshot" in source
    assert "ibkr_order_status_rule" in source
    assert "IBKRExecutionDetailsObservation" in source


def test_missing_provider_truth_degrades_snapshot_instead_of_fabricating() -> None:
    source = _READ_SIDE.read_text(encoding="utf-8")

    assert "SnapshotCompleteness.PARTIAL" in source
    assert "explicit account restriction evidence is unavailable" in source
    assert "position instrument mapping is unresolved" in source
    assert "order has no stable permId" in source
    assert "fill has no stable permId" in source


def test_startup_reconciliation_keeps_economic_write_admission_closed() -> None:
    source = _STARTUP.read_text(encoding="utf-8")

    assert 'name="economic_write_admission"' in source
    assert "real PAPER execution certification is not complete." in source
    assert "IBKR economic write path is not PAPER certified yet" in source


def test_ibkr_read_side_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRBrokerSnapshotPort",
        "IBKRReadSideClient",
        "IBKRStartupReconciliationGate",
        "IBKRInstrumentResolver",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_lot06_2_does_not_claim_real_paper_certification() -> None:
    source = _READ_SIDE.read_text(encoding="utf-8")
    startup = _STARTUP.read_text(encoding="utf-8")

    assert "CertifiedCapability" not in source
    assert "CertifiedCapability" not in startup
    assert "C3" not in source
    assert "C3" not in startup
