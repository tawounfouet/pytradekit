"""Helpers for architecture import analysis."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path("src/pytradekit")


def module_name(path: Path) -> str:
    """Return the Python module name for a package source file."""
    relative = path.relative_to(PACKAGE_ROOT.parent).with_suffix("")
    parts = list(relative.parts)

    if parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def python_sources() -> list[Path]:
    """Return project-authored Python package sources."""
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def imported_modules(path: Path) -> set[str]:
    """Return import targets declared by one source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = module_name(path)
    current_package = current if path.name == "__init__.py" else current.rpartition(".")[0]
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level == 0:
            if node.module is not None:
                imports.add(node.module)
            continue

        package_parts = current_package.split(".") if current_package else []
        keep = len(package_parts) - node.level + 1
        base_parts = package_parts[: max(keep, 0)]
        module_parts = node.module.split(".") if node.module else []
        resolved = ".".join([*base_parts, *module_parts])

        if resolved:
            imports.add(resolved)

    return imports


def package_import_graph() -> dict[str, set[str]]:
    """Build a graph containing only imports between PyTradeKit modules."""
    sources = python_sources()
    modules = {module_name(path) for path in sources}
    graph: dict[str, set[str]] = {module: set() for module in modules}

    for path in sources:
        source = module_name(path)

        for imported in imported_modules(path):
            target = imported

            while target and target not in modules:
                target = target.rpartition(".")[0]

            if target in modules and target != source:
                graph[source].add(target)

    return graph
