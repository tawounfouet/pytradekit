"""Architecture fitness functions for milestone 0.7 Security."""

from tests.architecture._imports import imported_modules, python_sources


def test_ff_036_security_domain_cannot_import_broker_adapters() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/security/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith("pytradekit.brokers.adapters"):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Broker adapter imports found in security.domain:\n"
        + "\n".join(offenders)
    )


def test_security_domain_cannot_import_sqlalchemy() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/security/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported == "sqlalchemy" or imported.startswith("sqlalchemy."):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "SQLAlchemy imports found in security.domain:\n"
        + "\n".join(offenders)
    )


def test_security_services_are_provider_and_infrastructure_independent() -> None:
    forbidden = ("pytradekit.brokers", "pytradekit.persistence", "sqlalchemy")
    offenders: list[str] = []
    for path in python_sources():
        if "/security/services/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith(forbidden):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Infrastructure imports found in security.services:\n"
        + "\n".join(offenders)
    )


def test_orders_do_not_import_security_directly() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/orders/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if (
                imported == "pytradekit.security"
                or imported.startswith("pytradekit.security.")
            ):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Direct Security imports found in Orders:\n"
        + "\n".join(offenders)
    )
