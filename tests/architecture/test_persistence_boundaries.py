"""Architecture fitness functions for milestone 0.5 persistence."""

from tests.architecture._imports import imported_modules, python_sources


def test_ff_021_sqlalchemy_is_forbidden_in_domain() -> None:
    """Domain modules must not depend on SQLAlchemy."""
    offenders: list[str] = []

    for path in python_sources():
        if "/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported == "sqlalchemy" or imported.startswith("sqlalchemy."):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "SQLAlchemy imports found in Domain:\n" + "\n".join(offenders)


def test_persistence_ports_do_not_import_sqlalchemy() -> None:
    """Repository and transaction contracts remain infrastructure-neutral."""
    offenders: list[str] = []

    for path in python_sources():
        path_text = path.as_posix()
        if "/ports/" not in path_text:
            continue
        for imported in imported_modules(path):
            if imported == "sqlalchemy" or imported.startswith("sqlalchemy."):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "SQLAlchemy imports found in ports:\n" + "\n".join(offenders)
