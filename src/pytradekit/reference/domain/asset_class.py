"""Asset class enumeration for canonical instruments."""

from enum import StrEnum


class AssetClass(StrEnum):
    """Canonical asset classes supported by the 0.1 reference model."""

    EQUITY = "equity"
    ETF = "etf"
    FX = "fx"
    CRYPTO = "crypto"
    FUTURE = "future"
    OPTION = "option"
    CFD = "cfd"
