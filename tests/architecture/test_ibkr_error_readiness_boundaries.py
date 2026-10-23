"""Architecture fitness functions for IBKR LOT-05.7."""

from pathlib import Path

_ERROR_READINESS = Path(
    "src/pytradekit/brokers/adapters/ibkr/error_readiness.py"
)
_MANIFEST = Path(
    "src/pytradekit/brokers/adapters/ibkr/capability_manifest.py"
)
_CANONICAL_ROOTS = (
    Path("src/pytradekit/portfolio"),
    Path("src/pytradekit/reference"),
    Path("src/pytradekit/orders"),
    Path("src/pytradekit/execution"),
    Path("src/pytradekit/risk"),
    Path("src/pytradekit/reconciliation"),
    Path("src/pytradekit/safety"),
    Path("src/pytradekit/strategy"),
)


def test_lot05_7_has_no_provider_sdk_import() -> None:
    source = _ERROR_READINESS.read_text(encoding="utf-8") + _MANIFEST.read_text(
        encoding="utf-8"
    )

    assert "import ibapi" not in source
    assert "from ibapi" not in source
    assert "import ib_async" not in source
    assert "from ib_async" not in source


def test_ibkr_lot05_7_types_do_not_leak_into_canonical_layers() -> None:
    forbidden = (
        "IBKRErrorObservation",
        "IBKRErrorRule",
        "IBKRReadinessObservation",
        "IBKRReadinessDecision",
        "IBKRConnectivityState",
    )
    violations: list[str] = []

    for root in _CANONICAL_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(name in source for name in forbidden):
                violations.append(str(path))

    assert violations == []


def test_ibkr_capability_manifest_does_not_claim_live_or_sdk_transport() -> None:
    source = _MANIFEST.read_text(encoding="utf-8")

    assert 'RuntimeEnvironment.PAPER' in source
    assert 'RuntimeEnvironment.LIVE' not in source
    assert "sdk_name=None" in source
    assert "sdk_version=None" in source


def test_unknown_error_path_fails_closed_instead_of_blind_retry() -> None:
    source = _ERROR_READINESS.read_text(encoding="utf-8")

    assert "ProviderProtocolError" in source
    assert "ProviderUncertainOutcomeError" in source
    assert "time.sleep(" not in source
    assert "retry(" not in source
