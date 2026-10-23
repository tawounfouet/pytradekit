"""Public contract for IBKR LOT-06.6 operational runtime."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_MARKET_RULE_VERSION,
    IBKR_OPERATIONAL_RUNTIME_VERSION,
    IBKR_QUALIFIED_MAX_REQUEST_RATE_PER_SECOND,
    IBKRMarketRule,
    IBKRMarketRuleClient,
    IBKRMarketRuleError,
    IBKRMarketRuleResolution,
    IBKRMarketRuleResolver,
    IBKRMarketRuleValidationEvidence,
    IBKROperationalEventBridge,
    IBKROperationalGuard,
    IBKROperationalRuntime,
    IBKROperationalRuntimeError,
    IBKROperationalSnapshot,
    IBKRPacingEvidence,
    IBKRPriceIncrement,
    IBKRReconnectRecoveryEvidence,
    IBKRReconnectRecoveryRuntime,
    IBKRReconnectReconciliation,
    IBKRRuntimeMarketRuleClient,
    build_ibkr_market_rule_resolver,
    build_ibkr_operational_runtime,
    ibkr_routing_market_rule_id,
    normalize_ibkr_market_rule,
    qualify_ib_async_pacing,
)


def test_ibkr_lot06_6_public_surface_is_exported() -> None:
    assert IBKR_MARKET_RULE_VERSION == "0.8.0b7-lot06.6"
    assert IBKR_OPERATIONAL_RUNTIME_VERSION == "0.8.0b7-lot06.6"
    assert IBKR_QUALIFIED_MAX_REQUEST_RATE_PER_SECOND == 45.0
    assert IBKRMarketRule.__name__ == "IBKRMarketRule"
    assert IBKRMarketRuleClient.__name__ == "IBKRMarketRuleClient"
    assert issubclass(IBKRMarketRuleError, ValueError)
    assert IBKRMarketRuleResolution.__name__ == "IBKRMarketRuleResolution"
    assert IBKRMarketRuleResolver.__name__ == "IBKRMarketRuleResolver"
    assert IBKRMarketRuleValidationEvidence.__name__ == (
        "IBKRMarketRuleValidationEvidence"
    )
    assert IBKRPriceIncrement.__name__ == "IBKRPriceIncrement"
    assert IBKRRuntimeMarketRuleClient.__name__ == (
        "IBKRRuntimeMarketRuleClient"
    )
    assert IBKROperationalEventBridge.__name__ == (
        "IBKROperationalEventBridge"
    )
    assert IBKROperationalGuard.__name__ == "IBKROperationalGuard"
    assert IBKROperationalRuntime.__name__ == "IBKROperationalRuntime"
    assert issubclass(IBKROperationalRuntimeError, ValueError)
    assert IBKROperationalSnapshot.__name__ == "IBKROperationalSnapshot"
    assert IBKRPacingEvidence.__name__ == "IBKRPacingEvidence"
    assert IBKRReconnectRecoveryEvidence.__name__ == (
        "IBKRReconnectRecoveryEvidence"
    )
    assert IBKRReconnectRecoveryRuntime.__name__ == (
        "IBKRReconnectRecoveryRuntime"
    )
    assert IBKRReconnectReconciliation.__name__ == (
        "IBKRReconnectReconciliation"
    )
    assert callable(build_ibkr_market_rule_resolver)
    assert callable(build_ibkr_operational_runtime)
    assert callable(ibkr_routing_market_rule_id)
    assert callable(normalize_ibkr_market_rule)
    assert callable(qualify_ib_async_pacing)
