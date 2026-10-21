"""Unit tests for AssetClass."""

from pytradekit.reference import AssetClass


def test_asset_class_exposes_canonical_values() -> None:
    assert AssetClass.EQUITY.value == "equity"
    assert AssetClass.ETF.value == "etf"
    assert AssetClass.FX.value == "fx"
    assert AssetClass.CRYPTO.value == "crypto"
    assert AssetClass.FUTURE.value == "future"
    assert AssetClass.OPTION.value == "option"
    assert AssetClass.CFD.value == "cfd"
