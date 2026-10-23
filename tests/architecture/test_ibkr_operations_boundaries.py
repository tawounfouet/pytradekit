"""Architecture fitness functions for IBKR LOT-06.6 operations."""

from pathlib import Path

_MARKET_RULES = Path(
    "src/pytradekit/brokers/adapters/ibkr/market_rules.py"
)
_OPERATIONS = Path(
    "src/pytradekit/brokers/adapters/ibkr/operations_runtime.py"
)
_EXECUTION = Path(
    "src/pytradekit/brokers/adapters/ibkr/execution.py"
)


def test_market_rule_runtime_has_one_provider_request_call_site() -> None:
    source = _MARKET_RULES.read_text(encoding="utf-8")

    assert source.count("request.reqMarketRule(") == 1


def test_dynamic_market_rule_validation_happens_before_place_order() -> None:
    source = _EXECUTION.read_text(encoding="utf-8")

    validation = source.index("self._market_rules.validate_limit_price(")
    provider_write = source.index("client.placeOrder(")

    assert validation < provider_write
    assert "if not evidence.valid:" in source


def test_operational_guard_runs_before_submit_and_cancel_provider_calls() -> None:
    source = _EXECUTION.read_text(encoding="utf-8")

    submit_guard = source.index(
        'self._operations.require_write_allowed(operation="submit")'
    )
    place_order = source.index("client.placeOrder(")
    cancel_guard = source.index(
        'self._operations.require_write_allowed(operation="cancel")'
    )
    cancel_order = source.index("client.cancelOrder(")

    assert submit_guard < place_order
    assert cancel_guard < cancel_order


def test_lot06_6_does_not_add_automatic_reconnect_or_write_replay() -> None:
    operations = _OPERATIONS.read_text(encoding="utf-8")
    execution = _EXECUTION.read_text(encoding="utf-8")

    assert "Watchdog" not in operations
    assert "time.sleep(" not in operations
    assert ".placeOrder(" not in operations
    assert ".cancelOrder(" not in operations
    assert execution.count("client.placeOrder(") == 1
    assert execution.count("client.cancelOrder(") == 1


def test_pacing_uses_ib_async_throttle_evidence_instead_of_second_queue() -> None:
    source = _OPERATIONS.read_text(encoding="utf-8")

    assert "MaxRequests" in source
    assert "RequestsInterval" in source
    assert "throttleStart" in source
    assert "throttleEnd" in source
    assert "IBKR_QUALIFIED_MAX_REQUEST_RATE_PER_SECOND = 45.0" in source
    assert "asyncio.Queue" not in source


def test_connectivity_transitions_cover_frozen_system_codes() -> None:
    source = _OPERATIONS.read_text(encoding="utf-8")

    for code in ("1100", "1101", "1102", "1300", "2103", "2104"):
        assert code in source


def test_reconnect_recovery_reconciles_before_readmission() -> None:
    source = _OPERATIONS.read_text(encoding="utf-8")

    reconciliation = source.index("outcome = self._reconciliation.reconnect()")
    readmission = source.index("self._operations.guard.mark_reconciled()")

    assert reconciliation < readmission


def test_lot06_6_keeps_certification_and_live_out_of_scope() -> None:
    market_rules = _MARKET_RULES.read_text(encoding="utf-8")
    operations = _OPERATIONS.read_text(encoding="utf-8")

    assert "CertifiedCapability" not in market_rules
    assert "CertifiedCapability" not in operations
    assert "C3" not in market_rules
    assert "C3" not in operations
    assert "LIVE" not in market_rules
    assert "LIVE" not in operations
