"""Architecture fitness functions for operational health."""

from tests.architecture._imports import imported_modules, python_sources


def test_ff_043_health_code_cannot_mutate_trading_aggregates() -> None:
    forbidden_prefixes = (
        "pytradekit.orders.domain",
        "pytradekit.portfolio.domain",
        "pytradekit.risk.domain",
        "pytradekit.execution",
    )
    offenders: list[str] = []
    for path in python_sources():
        if "/operations/domain/" not in path.as_posix() and (
            "/operations/services/health_registry.py" not in path.as_posix()
        ):
            continue
        for imported in imported_modules(path):
            if imported.startswith(forbidden_prefixes):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Operational health imports trading aggregate code:\n"
        + "\n".join(offenders)
    )


def test_health_checks_are_read_only_dependency_ports() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/operations/adapters/health_checks.py" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith("pytradekit.orders") or imported.startswith(
                "pytradekit.portfolio"
            ):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Health checks depend on trading aggregates:\n"
        + "\n".join(offenders)
    )
