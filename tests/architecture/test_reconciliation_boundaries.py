"""Architecture fitness functions for milestone 0.6 reconciliation."""

from tests.architecture._imports import imported_modules, python_sources


def test_ff_027_reconciliation_domain_cannot_import_broker_adapters() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/reconciliation/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith("pytradekit.brokers.adapters"):
                offenders.append(f"{path}: {imported}")
    assert not offenders, "Broker adapter imports found in reconciliation.domain:\n" + "\n".join(
        offenders
    )


def test_ff_028_reconciliation_domain_cannot_import_sqlalchemy() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/reconciliation/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported == "sqlalchemy" or imported.startswith("sqlalchemy."):
                offenders.append(f"{path}: {imported}")
    assert not offenders, "SQLAlchemy imports found in reconciliation.domain:\n" + "\n".join(
        offenders
    )
