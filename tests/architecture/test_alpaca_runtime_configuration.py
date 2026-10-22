"""Architecture safety checks for LOT-05 Alpaca PAPER runtime configuration."""

from pathlib import Path

RUNTIME_PATH = Path("src/pytradekit/brokers/adapters/alpaca/runtime.py")
CONFIG_PATH = Path("src/pytradekit/runtime/configuration.py")
SCRIPT_PATH = Path("scripts/alpaca_paper_runtime_readiness.py")


def test_lot05_runtime_has_no_live_endpoint_or_live_mode() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")
    config = CONFIG_PATH.read_text(encoding="utf-8")

    assert "TRADING_LIVE" not in source
    assert "api.alpaca.markets" not in source
    assert "LIVE =" not in config
    assert "paper=True" in source


def test_lot05_command_client_forces_sdk_retries_to_zero() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "self._retry = 0" in source


def test_lot05_readiness_script_exposes_no_trading_command() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    forbidden = (
        "submit_order",
        "cancel_order_by_id",
        "replace_order_by_id",
        "close_position",
        "close_all_positions",
    )
    assert all(name not in source for name in forbidden)


def test_lot05_runtime_never_resolves_secrets_directly_from_os_environ() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "os.environ" not in source
    assert "os.getenv" not in source
    assert ".resolve(profile.api_key_ref)" in source
    assert ".resolve(profile.api_secret_ref)" in source
    assert ".resolve(profile.database_url_ref)" in source
