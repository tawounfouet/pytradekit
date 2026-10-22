"""Architecture fitness functions for LOT-06 observability."""

from pathlib import Path

from tests.architecture._imports import imported_modules, python_sources


def test_ff_044_telemetry_exporter_cannot_import_economic_mutation_paths() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/operations/adapters/tracing.py" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith(
                (
                    "pytradekit.orders",
                    "pytradekit.portfolio",
                    "pytradekit.risk",
                    "pytradekit.execution",
                )
            ):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Trace exporter imports economic mutation paths:\n"
        + "\n".join(offenders)
    )


def test_ff_045_telemetry_surfaces_have_explicit_secret_guards() -> None:
    required = {
        "src/pytradekit/runtime/observability.py": "_FORBIDDEN_VALUE_MARKERS",
        "src/pytradekit/operations/domain/trace.py": "_SECRET_MARKERS",
        "src/pytradekit/operations/domain/alert.py": "_SECRET_MARKERS",
    }
    missing = [
        f"{path}: {marker}"
        for path, marker in required.items()
        if marker not in Path(path).read_text(encoding="utf-8")
    ]
    assert not missing, (
        "Telemetry secret guard missing:\n"
        + "\n".join(missing)
    )


def test_ff_046_alert_sink_is_not_imported_by_domain_packages() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/domain/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith("pytradekit.operations.ports"):
                offenders.append(f"{path}: {imported}")
    assert not offenders, (
        "Domain package imports alert or tracing ports:\n"
        + "\n".join(offenders)
    )
