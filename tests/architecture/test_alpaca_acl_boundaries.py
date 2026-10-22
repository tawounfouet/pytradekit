"""Architecture fitness functions for the Alpaca anti-corruption layer."""

from __future__ import annotations

import ast
from pathlib import Path

ALPACA_ADAPTER = Path("src/pytradekit/brokers/adapters/alpaca")
MAPPERS = ALPACA_ADAPTER / "mappers.py"
GENERIC_MODELS = Path("src/pytradekit/brokers/models.py")
GENERIC_ERRORS = Path("src/pytradekit/brokers/errors.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_provider_neutral_broker_models_import_no_alpaca_sdk() -> None:
    assert all(not name.startswith("alpaca") for name in _imports(GENERIC_MODELS))
    assert all(not name.startswith("alpaca") for name in _imports(GENERIC_ERRORS))


def test_alpaca_sdk_is_confined_to_adapter_package() -> None:
    package_root = Path("src/pytradekit")
    offenders: list[str] = []
    for path in package_root.rglob("*.py"):
        if ALPACA_ADAPTER in path.parents:
            continue
        for imported in _imports(path):
            if imported == "alpaca" or imported.startswith("alpaca."):
                offenders.append(f"{path}: {imported}")
    assert not offenders, "Alpaca SDK leaked outside adapter:\n" + "\n".join(offenders)


def test_acl_never_uses_provider_id_as_canonical_instrument_or_account_id() -> None:
    source = MAPPERS.read_text(encoding="utf-8")

    assert "InstrumentId.from_string(str(asset.id))" not in source
    assert "AccountId.from_string(str(account.id))" not in source
    assert "instrument_id: InstrumentId" in source
    assert "account_id: AccountId" in source


def test_acl_never_converts_economic_truth_through_float() -> None:
    tree = ast.parse(MAPPERS.read_text(encoding="utf-8"), filename=str(MAPPERS))
    float_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "float"
    ]

    assert float_calls == []


def test_order_query_mapper_does_not_fabricate_fill_from_cumulative_order_fields() -> None:
    source = MAPPERS.read_text(encoding="utf-8")

    assert "does not identify individual executions" in source
    assert "ProviderStateReconciliationRequired" in source
