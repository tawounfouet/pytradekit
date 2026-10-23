"""Architecture fitness functions for IBKR LOT-04 discovery."""

from pathlib import Path

_IBKR_DISCOVERY = Path("src/pytradekit/brokers/adapters/ibkr/discovery.py")
_PYPROJECT = Path("pyproject.toml")
_CORE_ROOTS = (
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
)


def test_ibkr_discovery_remains_sdk_free_with_optional_runtime_transport() -> None:
    source = _IBKR_DISCOVERY.read_text(encoding="utf-8")
    pyproject = _PYPROJECT.read_text(encoding="utf-8").lower()

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source
    assert "ibapi" not in pyproject
    assert 'ibkr = ["ib_async==2.1.0"]' in pyproject


def test_ibkr_semantics_do_not_enter_canonical_core() -> None:
    violations: list[str] = []

    for root in _CORE_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8").lower()
            if "ibkr" in source or "interactive brokers" in source:
                violations.append(str(path))

    assert violations == []


def test_lot04_discovery_contains_no_certification_or_live_runtime() -> None:
    source = _IBKR_DISCOVERY.read_text(encoding="utf-8")

    assert "CertifiedCapability" not in source
    assert "RuntimeEnvironment.LIVE" not in source
    assert "paper=False" not in source


def test_order_id_and_perm_id_roles_are_explicitly_distinct() -> None:
    source = _IBKR_DISCOVERY.read_text(encoding="utf-8")

    assert 'SESSION_ORDER_ID = "orderId"' in source
    assert 'PERMANENT_ORDER_ID = "permId"' in source
    assert "external_order_id_field=IBKROrderIdentityRole.PERMANENT_ORDER_ID.value" in source
