"""Architecture fitness functions for IBKR LOT-06.5 economic writes."""

from pathlib import Path

_SOURCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/execution.py"
)
_CANONICAL_ROOTS = (
    Path("src/pytradekit/reference/domain"),
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution/domain"),
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation/domain"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_place_order_has_one_provider_call_site() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert source.count("client.placeOrder(") == 1


def test_cancel_order_has_one_provider_call_site() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert source.count("client.cancelOrder(") == 1


def test_execution_adapter_has_no_retry_loop_or_retry_library() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "for attempt in" not in source
    assert "while True" not in source
    assert "tenacity" not in source
    assert "backoff" not in source
    assert "retry(" not in source


def test_economic_write_requires_explicit_admission() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "IBKREconomicWriteAdmission" in source
    assert 'self._admission.require(operation="submit")' in source
    assert 'self._admission.require(operation="cancel")' in source


def test_place_order_uses_pre_reserved_session_order_id() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert '"orderId": reservation.session_order_id.value' in source
    assert "self._session.reserve(context)" in source


def test_dynamic_market_rule_limit_is_fail_closed_before_write() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "IBKRPriceIncrementMode.MARKET_RULE" in source
    assert "dynamic market-rule" in source


def test_order_id_is_not_emitted_as_canonical_external_order_id() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "external_order_id=str(permanent_order_id)" in source
    assert "external_order_id=str(reservation.session_order_id)" not in source


def test_ib_async_is_loaded_only_inside_ibkr_boundary() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert 'import_module("ib_async")' in source
    assert "from ib_async" not in source
    assert "import ib_async" not in source


def test_execution_runtime_does_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRExecutionAdapter",
        "IBKREconomicWriteAdmission",
        "IBKRSDKPlacementFactory",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_lot06_5_does_not_claim_paper_certification_or_live() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert "CertifiedCapability" not in source
    assert "C3" not in source
    assert "LIVE" not in source
