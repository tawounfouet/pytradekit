"""Architecture fitness functions for IBKR LOT-06.1 transport runtime."""

from pathlib import Path

_RUNTIME = Path("src/pytradekit/brokers/adapters/ibkr/runtime.py")
_PYPROJECT = Path("pyproject.toml")
_CANONICAL_ROOTS = (
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/reference"),
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_ibkr_transport_is_optional_and_exactly_pinned() -> None:
    pyproject = _PYPROJECT.read_text(encoding="utf-8")

    assert 'ibkr = ["ib_async==2.1.0"]' in pyproject


def test_runtime_does_not_import_official_ibapi() -> None:
    source = _RUNTIME.read_text(encoding="utf-8")

    assert "import ibapi" not in source
    assert "from ibapi" not in source


def test_runtime_loads_ib_async_only_inside_provider_boundary() -> None:
    source = _RUNTIME.read_text(encoding="utf-8")

    assert 'IBKR_ASYNC_PACKAGE_NAME = "ib_async"' in source
    assert "import_module(IBKR_ASYNC_PACKAGE_NAME)" in source
    assert "from ib_async" not in source
    assert "import ib_async" not in source


def test_runtime_does_not_modify_alpaca_only_core_runtime_profile() -> None:
    source = Path("src/pytradekit/runtime/configuration.py").read_text(
        encoding="utf-8"
    )

    assert "IBKR" not in source
    assert "ibkr" not in source


def test_ibkr_runtime_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRPaperRuntimeProfile",
        "IBKRPaperConnectionRuntime",
        "IBAsyncPaperTransport",
        "IBKRTransportConnectionEvidence",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_runtime_has_no_live_port_or_live_fallback() -> None:
    source = _RUNTIME.read_text(encoding="utf-8")

    assert "4001" not in source
    assert "7496" not in source
    assert "RuntimeEnvironment.LIVE" not in source


def test_client_zero_is_explicitly_rejected() -> None:
    source = _RUNTIME.read_text(encoding="utf-8")

    assert "client_id 0 is forbidden" in source
