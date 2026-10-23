"""Architecture fitness functions for IBKR LOT-06.3 reference resolution."""

from pathlib import Path

_SOURCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/contract_resolution.py"
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


def test_contract_resolution_has_no_economic_write_call() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert ".placeOrder(" not in source
    assert ".cancelOrder(" not in source
    assert "place_order" not in source
    assert "cancel_order" not in source


def test_contract_resolution_queries_by_con_id() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "reqContractDetails" in source
    assert "conId=contract_id.value" in source
    assert 'exchange="SMART"' in source


def test_contract_resolution_does_not_fabricate_canonical_identity() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "InstrumentId.new()" not in source
    assert "IBKRCanonicalInstrumentIdResolver" in source


def test_contract_resolution_preserves_lot05_market_rule_semantics() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "marketRuleIds" in source
    assert "validExchanges" in source
    assert "map_ibkr_stock_contract" in source
    assert "IBKRPriceIncrementMode" in source


def test_provider_sdk_is_loaded_only_inside_ibkr_adapter_boundary() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert 'import_module("ib_async")' in source
    assert "from ib_async" not in source
    assert "import ib_async" not in source


def test_ibkr_reference_runtime_does_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRContractReferenceResolver",
        "IBKRContractResolutionEvidence",
        "IBKRRuntimeContractDetailsClient",
        "IBAsyncContractRequestFactory",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_lot06_3_does_not_claim_paper_certification() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "CertifiedCapability" not in source
    assert "C3" not in source
    assert "LIVE" not in source
