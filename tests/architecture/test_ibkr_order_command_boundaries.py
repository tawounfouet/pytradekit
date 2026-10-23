"""Architecture fitness functions for IBKR LOT-05.3 order command mapping."""

from pathlib import Path

_COMMANDS = Path("src/pytradekit/brokers/adapters/ibkr/order_commands.py")
_CANONICAL_ROOTS = (
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_order_command_mapper_has_no_provider_sdk_import() -> None:
    source = _COMMANDS.read_text(encoding="utf-8")

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_order_command_has_no_session_order_id_allocation() -> None:
    source = _COMMANDS.read_text(encoding="utf-8")

    assert "nextValidId" not in source
    assert "IBKRSessionOrderId" not in source
    assert "IBKRClientId" not in source


def test_ibkr_order_command_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKROrderCommand",
        "IBKRPlacementCommand",
        "IBKROrderAction",
        "IBKROrderType",
        "IBKRTimeInForce",
        "IBKRTransmitPolicy",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_execution_port_remains_ibkr_free() -> None:
    source = Path("src/pytradekit/orders/ports/execution_port.py").read_text(
        encoding="utf-8"
    )

    assert "IBKR" not in source
    assert "placeOrder" not in source
    assert "orderRef" not in source
