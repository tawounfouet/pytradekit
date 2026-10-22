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


def test_ff_040_kill_switch_code_cannot_submit_flatten_orders() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/safety/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.endswith("execution_port") or imported.endswith("submit_order"):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Safety governance imports execution mutation paths:\n"
        + "\n".join(offenders)
    )


def test_ff_041_override_policy_checks_kill_switch_before_override() -> None:
    path = Path("src/pytradekit/safety/services/policy.py")
    source = path.read_text(encoding="utf-8")

    derive_index = source.index("kill_switch_active")
    override_index = source.index("risk_override_active")

    assert derive_index < override_index


def test_ff_042_unknown_truth_is_evaluated_before_risk_override() -> None:
    path = Path("src/pytradekit/safety/services/policy.py")
    source = path.read_text(encoding="utf-8")

    unknown_index = source.index("ConsistencyStatus.UNKNOWN")
    override_index = source.index("risk_override_active")

    assert unknown_index < override_index
