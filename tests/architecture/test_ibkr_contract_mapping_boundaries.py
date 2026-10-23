"""Architecture fitness functions for IBKR LOT-05.2 contract mapping."""

from pathlib import Path

_IBKR_MAPPING = Path("src/pytradekit/brokers/adapters/ibkr/contract_mapping.py")
_CANONICAL_ROOTS = (
    Path("src/pytradekit/reference"),
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_contract_mapper_has_no_provider_sdk_import() -> None:
    source = _IBKR_MAPPING.read_text(encoding="utf-8")

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_ibkr_contract_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRContractRecord",
        "IBKRContractDetailsRecord",
        "IBKRInstrumentMappingResult",
        "IBKRPriceIncrementMode",
        "IBKRSecurityType",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_canonical_contract_specification_remains_provider_neutral() -> None:
    source = Path(
        "src/pytradekit/reference/domain/contract_specification.py"
    ).read_text(encoding="utf-8")

    assert "IBKR" not in source
    assert "marketRule" not in source
    assert "minTick" not in source
    assert "SMART" not in source
