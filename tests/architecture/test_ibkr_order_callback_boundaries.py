"""Architecture fitness functions for IBKR LOT-05.4 callback normalization."""

from pathlib import Path

_CALLBACKS = Path("src/pytradekit/brokers/adapters/ibkr/order_callbacks.py")
_CANONICAL_ROOTS = (
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_callback_normalizer_has_no_provider_sdk_import() -> None:
    source = _CALLBACKS.read_text(encoding="utf-8")

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_ibkr_callback_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKROpenOrderObservation",
        "IBKROrderStatusObservation",
        "IBKROrderErrorObservation",
        "IBKROrderStateRule",
        "IBKROrderStatus",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_callback_normalizer_does_not_create_fill() -> None:
    source = _CALLBACKS.read_text(encoding="utf-8")

    assert "Fill(" not in source
    assert "FillId(" not in source
    assert "execDetails" in source


def test_inactive_has_no_direct_rejected_mapping() -> None:
    source = _CALLBACKS.read_text(encoding="utf-8")

    assert "IBKROrderStatus.INACTIVE.value: IBKROrderStateRule(" in source
    assert "IBKROrderStateDisposition.RECONCILE" in source
