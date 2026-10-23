"""Regression tests for the real IBKR PAPER probe coordination helpers."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

from pytradekit.brokers.adapters.ibkr import IBKRContractId, IBKRPaperRuntimeProfile


def _load_probe_module() -> ModuleType:
    path = Path("scripts/ibkr_paper_controlled_probe.py")
    spec = importlib.util.spec_from_file_location(
        "_pytradekit_ibkr_paper_probe_test",
        path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_probe = _load_probe_module()
_wait_position_quantity = cast(
    Callable[..., Decimal],
    getattr(_probe, "_wait_position_quantity"),
)


class _LaggingPortfolioProvider:
    def __init__(self) -> None:
        self._position = 10
        self.sleep_calls = 0

    def portfolio(self, account: str = "") -> list[object]:
        return [
            SimpleNamespace(
                account=account,
                contract=SimpleNamespace(conId=265598),
                position=self._position,
            )
        ]

    def sleep(self, secs: float = 0.02) -> bool:
        _ = secs
        self.sleep_calls += 1
        self._position = 11
        return True


def test_wait_position_quantity_allows_bounded_provider_lag() -> None:
    provider = _LaggingPortfolioProvider()
    profile = IBKRPaperRuntimeProfile(expected_account_id="DU1234567")

    observed = _wait_position_quantity(
        provider=provider,
        profile=profile,
        contract_id=IBKRContractId(265598),
        expected=Decimal("11"),
        timeout_seconds=0.1,
    )

    assert observed == Decimal("11")
    assert provider.sleep_calls == 1
