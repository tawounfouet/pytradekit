"""Architecture fitness functions for OMS and Execution boundaries."""

from tests.architecture._imports import imported_modules, python_sources


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def test_ff_006_orders_domain_does_not_depend_on_brokers_or_execution() -> None:
    offenders: list[str] = []

    for path in python_sources():
        path_text = path.as_posix()
        if "/orders/domain/" not in path_text:
            continue
        for imported in imported_modules(path):
            if _matches(imported, "pytradekit.brokers") or _matches(
                imported, "pytradekit.execution"
            ):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Orders domain boundary violations found:\n" + "\n".join(offenders)


def test_ff_007_execution_domain_does_not_depend_on_brokers() -> None:
    offenders: list[str] = []

    for path in python_sources():
        if "/execution/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if _matches(imported, "pytradekit.brokers"):
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Execution domain boundary violations found:\n" + "\n".join(offenders)
