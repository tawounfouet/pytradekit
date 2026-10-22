"""Architecture fitness functions for Safety governance."""

from pathlib import Path

from tests.architecture._imports import imported_modules, python_sources


def test_ff_037_safety_domain_cannot_import_broker_adapters() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/safety/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith("pytradekit.brokers"):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Broker imports found in safety.domain:\n"
        + "\n".join(offenders)
    )


def test_ff_038_safety_gate_precedes_provider_submit() -> None:
    path = Path("src/pytradekit/orders/application/submit_order.py")
    source = path.read_text(encoding="utf-8")

    safety_index = source.index("self._safety_gate.evaluate_submit")
    provider_index = source.index("self._execution.submit")

    assert safety_index < provider_index


def test_orders_do_not_import_safety_bounded_context_directly() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/orders/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported == "pytradekit.safety" or imported.startswith(
                "pytradekit.safety."
            ):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Direct Safety imports found in Orders:\n"
        + "\n".join(offenders)
    )
