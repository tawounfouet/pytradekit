"""Regression tests for the real IBKR PAPER probe coordination helpers."""

from __future__ import annotations

from types import SimpleNamespace

from scripts import ibkr_paper_controlled_probe as probe

from pytradekit.brokers.adapters.ibkr import IBKRContractId, IBKRPaperRuntimeProfile


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

    observed = probe._wait_position_quantity(
        provider=provider,
        profile=profile,
        contract_id=IBKRContractId(265598),
        expected=probe.Decimal("11"),
        timeout_seconds=0.1,
    )

    assert observed == probe.Decimal("11")
    assert provider.sleep_calls == 1
