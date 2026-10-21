import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "pytradekit"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            result.add(node.module)
    return result


def test_strategy_domain_cannot_import_brokers_or_backtesting_adapters() -> None:
    for path in (ROOT / "strategy" / "domain").glob("*.py"):
        imports = _imports(path)
        assert not any(name.startswith("pytradekit.brokers") for name in imports)
        assert not any(name.startswith("pytradekit.backtesting.adapters") for name in imports)


def test_market_data_domain_cannot_import_strategy_or_brokers() -> None:
    for path in (ROOT / "market_data" / "domain").glob("*.py"):
        imports = _imports(path)
        assert not any(name.startswith("pytradekit.strategy") for name in imports)
        assert not any(name.startswith("pytradekit.brokers") for name in imports)
