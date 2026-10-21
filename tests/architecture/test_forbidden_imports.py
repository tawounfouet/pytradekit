"""Architecture checks for broker SDK isolation."""

from tests.architecture._imports import imported_modules, python_sources

BROKER_SDK_PREFIXES = (
    "alpaca",
    "ib_insync",
    "ibapi",
    "ctrader",
    "ctrader_open_api",
)


def _is_broker_adapter_path(path: str) -> bool:
    return "/brokers/" in path and "/adapters/" in path


def test_ff_003_broker_sdk_imports_are_isolated_to_broker_adapters() -> None:
    offenders: list[str] = []

    for path in python_sources():
        path_text = path.as_posix()

        if _is_broker_adapter_path(path_text):
            continue

        for imported in imported_modules(path):
            root = imported.split(".", maxsplit=1)[0]

            if root in BROKER_SDK_PREFIXES:
                offenders.append(f"{path}: {imported}")

    assert not offenders, "Broker SDK imports outside adapters found:\n" + "\n".join(offenders)
