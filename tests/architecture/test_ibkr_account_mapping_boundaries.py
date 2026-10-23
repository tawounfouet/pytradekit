"""Architecture fitness functions for IBKR LOT-05.6 account mapping."""

from pathlib import Path

_MAPPING = Path("src/pytradekit/brokers/adapters/ibkr/account_mapping.py")
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


def test_account_mapper_has_no_provider_sdk_import() -> None:
    source = _MAPPING.read_text(encoding="utf-8")

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_ibkr_account_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRAccountSummaryObservation",
        "IBKRAccountMetricTag",
        "IBKRAccountRestrictionsObservation",
        "IBKRPortfolioPositionObservation",
        "IBKRAccountMappingResult",
        "IBKRPositionMappingResult",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_available_funds_is_not_wired_to_balance_available() -> None:
    source = _MAPPING.read_text(encoding="utf-8")

    assert "available=None" in source
    assert "available=available_funds" not in source


def test_portfolio_value_is_not_fabricated_from_net_liquidation() -> None:
    source = _MAPPING.read_text(encoding="utf-8")

    assert "portfolio_value=None" in source
    assert "portfolio_value=net_liquidation" not in source


def test_position_availability_is_not_fabricated() -> None:
    source = _MAPPING.read_text(encoding="utf-8")

    assert "available_quantity=None" in source
