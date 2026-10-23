"""Architecture fitness functions for IBKR LOT-05.1 identity isolation."""

from pathlib import Path

_IBKR_ROOT = Path("src/pytradekit/brokers/adapters/ibkr")
_CANONICAL_ROOTS = (
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_identity_model_has_no_provider_sdk_import() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            _IBKR_ROOT / "identities.py",
            _IBKR_ROOT / "identity_registry.py",
        )
    )

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_ibkr_identity_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRClientId",
        "IBKRSessionOrderId",
        "IBKRPermanentOrderId",
        "IBKROrderReference",
        "IBKRExecutionId",
        "IBKRContractId",
        "IBKROrderIdentity",
        "IBKRExecutionIdentity",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_generic_provider_identity_models_remain_ibkr_free() -> None:
    source = Path("src/pytradekit/brokers/models.py").read_text(encoding="utf-8")

    assert "IBKR" not in source
    assert "orderRef" not in source
    assert "permId" not in source
    assert "execId" not in source
    assert "conId" not in source
    assert "clientId" not in source
