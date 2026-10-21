"""Architecture fitness functions for Portfolio and Risk."""

from tests.architecture._imports import imported_modules, python_sources


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def test_ff_010_portfolio_domain_does_not_depend_on_risk() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/portfolio/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if _matches(imported, "pytradekit.risk"):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Portfolio domain depends on Risk:\n" + "\n".join(offenders)


def test_ff_011_portfolio_domain_does_not_depend_on_brokers() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/portfolio/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if _matches(imported, "pytradekit.brokers"):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Portfolio domain depends on brokers:\n" + "\n".join(offenders)


def test_ff_012_risk_domain_does_not_depend_on_brokers() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/risk/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if _matches(imported, "pytradekit.brokers"):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Risk domain depends on brokers:\n" + "\n".join(offenders)


def test_ff_013_orders_domain_does_not_depend_on_risk() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/orders/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if _matches(imported, "pytradekit.risk"):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Orders domain depends on Risk:\n" + "\n".join(offenders)


def test_ff_014_portfolio_and_risk_domains_have_no_persistence_framework() -> None:
    forbidden = ("sqlalchemy", "psycopg", "alembic")
    offenders: list[str] = []
    for path in python_sources():
        path_text = path.as_posix()
        if "/portfolio/domain/" not in path_text and "/risk/domain/" not in path_text:
            continue
        for imported in imported_modules(path):
            if any(_matches(imported, prefix) for prefix in forbidden):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Persistence framework leaked into domains:\n" + "\n".join(offenders)
