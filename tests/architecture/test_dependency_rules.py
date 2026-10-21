"""Architecture fitness functions for dependency boundaries."""

from tests.architecture._imports import imported_modules, python_sources

FORBIDDEN_SHARED_PREFIXES = (
    "pytradekit.reference",
    "pytradekit.runtime",
    "pytradekit.testing",
)

FORBIDDEN_DOMAIN_PREFIXES = (
    "pytradekit.runtime.adapters",
    "pytradekit.testing",
    "sqlalchemy",
    "fastapi",
)


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def test_ff_001_domain_has_no_infrastructure_dependency() -> None:
    offenders: list[str] = []

    for path in python_sources():
        module = path.as_posix()

        if "/reference/domain/" not in module:
            continue

        for imported in imported_modules(path):
            if _matches_prefix(imported, FORBIDDEN_DOMAIN_PREFIXES):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Domain infrastructure dependencies found:\n" + "\n".join(offenders)


def test_ff_002_shared_kernel_does_not_depend_on_bounded_contexts() -> None:
    offenders: list[str] = []

    for path in python_sources():
        if "/shared/" not in path.as_posix():
            continue

        for imported in imported_modules(path):
            if _matches_prefix(imported, FORBIDDEN_SHARED_PREFIXES):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Shared Kernel boundary violations found:\n" + "\n".join(offenders)


def test_runtime_ports_do_not_depend_on_adapters() -> None:
    offenders: list[str] = []

    for path in python_sources():
        if "/runtime/ports/" not in path.as_posix():
            continue

        for imported in imported_modules(path):
            if imported == "pytradekit.runtime.adapters" or imported.startswith(
                "pytradekit.runtime.adapters."
            ):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Runtime port dependency violations found:\n" + "\n".join(offenders)
