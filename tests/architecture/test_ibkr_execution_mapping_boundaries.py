"""Architecture fitness functions for IBKR LOT-05.5 execution mapping."""

from pathlib import Path

_EXECUTIONS = Path("src/pytradekit/brokers/adapters/ibkr/execution_mapping.py")
_CANONICAL_ROOTS = (
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_execution_mapper_has_no_provider_sdk_import() -> None:
    source = _EXECUTIONS.read_text(encoding="utf-8")

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_execution_mapper_does_not_convert_financial_values_to_float() -> None:
    source = _EXECUTIONS.read_text(encoding="utf-8")

    assert "float(" not in source


def test_ibkr_execution_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRExecutionDetailsObservation",
        "IBKRExecutionRegistry",
        "IBKRExecutionDisposition",
        "IBKRExecutionSide",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_execution_corrections_are_not_mapped_as_second_fill() -> None:
    source = _EXECUTIONS.read_text(encoding="utf-8")

    assert "IBKRExecutionDisposition.CORRECTION" in source
    assert "do not emit a second" in source


def test_execution_time_parser_does_not_relabel_zoned_local_time_as_utc() -> None:
    source = _EXECUTIONS.read_text(encoding="utf-8")

    assert "first.astimezone(UTC)" in source
    assert "local_naive.replace(tzinfo=UTC)" not in source
