"""Architecture fitness functions for IBKR LOT-06.4 order sessions."""

from pathlib import Path

_SOURCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/order_session.py"
)
_CANONICAL_ROOTS = (
    Path("src/pytradekit/reference/domain"),
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation/domain"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_order_session_reserves_ids_without_economic_write() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "getReqId" in source
    assert ".placeOrder(" not in source
    assert ".cancelOrder(" not in source
    assert "place_order(" not in source
    assert "cancel_order(" not in source


def test_order_session_preserves_distinct_identity_roles() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "IBKRClientId" in source
    assert "IBKRSessionOrderId" in source
    assert "IBKROrderReference" in source
    assert "IBKRPermanentOrderId" in source
    assert "IBKROrderIdentityRegistry" in source


def test_callback_correlation_requires_preexisting_reservation() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "IBKROrderCorrelationRegistry" in source
    assert "return None" in source
    assert "reserved canonical order" in source


def test_order_session_does_not_import_ib_async_types() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "from ib_async" not in source
    assert "import ib_async" not in source


def test_order_session_does_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKROrderSessionRuntime",
        "IBKROrderSessionReservation",
        "IBKRCallbackCorrelationRouter",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_lot06_4_does_not_claim_economic_write_qualification() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "CertifiedCapability" not in source
    assert "C3" not in source
    assert "TRADING_READY" not in source
