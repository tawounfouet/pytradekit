"""Risk policy scopes."""

from enum import StrEnum


class RiskScope(StrEnum):
    """Scopes supported by milestone 0.3 risk policies."""

    GLOBAL = "global"
    PORTFOLIO = "portfolio"
    ACCOUNT = "account"
    STRATEGY = "strategy"
    BROKER = "broker"
    ASSET_CLASS = "asset_class"
    INSTRUMENT = "instrument"
