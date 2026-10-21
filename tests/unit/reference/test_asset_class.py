"""Unit tests for AssetClass."""

from pytradekit.reference import AssetClass


def test_asset_class_exposes_canonical_values() -> None:
    assert AssetClass.EQUITY == "equity"
    assert AssetClass.ETF == "etf"
    assert AssetClass.FX == "fx"
    assert AssetClass.CRYPTO == "crypto"
    assert AssetClass.FUTURE == "future"
    assert AssetClass.OPTION == "option"
    assert AssetClass.CFD == "cfd"
