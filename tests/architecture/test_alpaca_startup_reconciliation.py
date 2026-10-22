"""Architecture fitness functions for LOT-09 startup and recovery."""

from pathlib import Path

STARTUP_PATH = Path("src/pytradekit/brokers/adapters/alpaca/startup.py")
STREAM_PATH = Path("src/pytradekit/brokers/adapters/alpaca/stream.py")
RUNTIME_PATH = Path("src/pytradekit/brokers/adapters/alpaca/runtime.py")


def test_startup_reconciliation_never_submits_or_cancels_orders() -> None:
    source = STARTUP_PATH.read_text(encoding="utf-8")

    forbidden = (
        "submit_order",
        "cancel_order_by_id",
        "replace_order_by_id",
        "close_position",
        "close_all_positions",
    )
    assert all(item not in source for item in forbidden)


def test_startup_declares_trading_ready_only_after_stream_and_second_reconciliation() -> None:
    source = STARTUP_PATH.read_text(encoding="utf-8")

    stream_position = source.index("stream_ready = self._stream.start")
    second_position = source.index("post_stream_gaps = self._reconcile_cycle()")
    report_position = source.rindex("return self._report(checks, gaps)")

    assert stream_position < second_position < report_position


def test_trade_update_pipeline_contains_atomic_inbox_fill_portfolio_outbox_steps() -> None:
    source = STREAM_PATH.read_text(encoding="utf-8")

    required = (
        "uow.inbox.claim",
        "uow.fills.add",
        "HandleExecutionReport",
        "ApplyFillToPortfolio",
        "uow.outbox.add",
        "uow.inbox.mark_processed",
        "uow.commit()",
    )
    assert all(item in source for item in required)


def test_private_stream_is_hard_locked_to_paper() -> None:
    source = STREAM_PATH.read_text(encoding="utf-8")

    assert "paper=True" in source
    assert "TRADING_STREAM_LIVE" not in source


def test_trade_update_processor_contains_no_economic_command_transport() -> None:
    source = STREAM_PATH.read_text(encoding="utf-8")

    forbidden = (
        "submit_order",
        "cancel_order_by_id",
        "replace_order_by_id",
    )
    assert all(item not in source for item in forbidden)


def test_runtime_composition_includes_private_trade_stream() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "trade_stream: AlpacaPaperTradeStream" in source
    assert "trade_stream = AlpacaPaperTradeStream(api_key, secret_key)" in source


def test_no_live_environment_is_introduced_by_lot09() -> None:
    combined = (
        STARTUP_PATH.read_text(encoding="utf-8")
        + STREAM_PATH.read_text(encoding="utf-8")
        + RUNTIME_PATH.read_text(encoding="utf-8")
    )

    assert "TRADING_STREAM_LIVE" not in combined
    assert "paper=False" not in combined


def test_runtime_startup_delegates_to_generic_reconciliation_gate() -> None:
    source = STARTUP_PATH.read_text(encoding="utf-8")

    baseline_position = source.index("baseline = self.coordinator.start()")
    generic_position = source.index("return self.reconciliation.startup(baseline)")

    assert baseline_position < generic_position
