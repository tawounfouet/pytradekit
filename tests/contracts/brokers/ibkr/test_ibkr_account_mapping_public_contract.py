"""Public contract for IBKR account and position mapping."""

from pytradekit.brokers.adapters.ibkr import (
    IBKRAccountMappingError,
    IBKRAccountMappingResult,
    IBKRAccountMetric,
    IBKRAccountMetricTag,
    IBKRAccountRestrictionsObservation,
    IBKRAccountSummaryObservation,
    IBKRPortfolioPositionObservation,
    IBKRPositionMappingResult,
    map_ibkr_account_snapshot,
    map_ibkr_position_snapshot,
)


def test_ibkr_account_mapping_surface_is_public() -> None:
    assert IBKRAccountMetricTag.TOTAL_CASH_VALUE.value == "TotalCashValue"
    assert IBKRAccountMetricTag.NET_LIQUIDATION.value == "NetLiquidation"
    assert IBKRAccountMetricTag.BUYING_POWER.value == "BuyingPower"
    assert IBKRAccountMetricTag.AVAILABLE_FUNDS.value == "AvailableFunds"
    assert IBKRAccountMetricTag.CASH_BALANCE.value == "CashBalance"
    assert IBKRAccountMetric.__name__ == "IBKRAccountMetric"
    assert IBKRAccountSummaryObservation.__name__ == "IBKRAccountSummaryObservation"
    assert (
        IBKRAccountRestrictionsObservation.__name__
        == "IBKRAccountRestrictionsObservation"
    )
    assert IBKRAccountMappingResult.__name__ == "IBKRAccountMappingResult"
    assert (
        IBKRPortfolioPositionObservation.__name__
        == "IBKRPortfolioPositionObservation"
    )
    assert IBKRPositionMappingResult.__name__ == "IBKRPositionMappingResult"
    assert issubclass(IBKRAccountMappingError, ValueError)
    assert callable(map_ibkr_account_snapshot)
    assert callable(map_ibkr_position_snapshot)
