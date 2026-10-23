"""Public contract for IBKR error, readiness, and capability declarations."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ACL_ADAPTER_VERSION,
    IBKR_ACL_DECLARED_CAPABILITIES,
    IBKR_ERROR_RULES,
    IBKRConnectivityState,
    IBKRErrorCategory,
    IBKRErrorDisposition,
    IBKRErrorMappingError,
    IBKRErrorObservation,
    IBKRErrorRule,
    IBKRReadinessDecision,
    IBKRReadinessObservation,
    assert_ibkr_ready_for_economic_write,
    build_ibkr_capability_manifest,
    evaluate_ibkr_readiness,
    ibkr_connectivity_state,
    ibkr_error_rule,
    map_ibkr_provider_error,
    validate_ibkr_capability_manifest,
)


def test_ibkr_lot05_7_public_surface_is_exported() -> None:
    assert IBKR_ACL_ADAPTER_VERSION == "0.8.0b1-lot05.7"
    assert IBKR_ACL_DECLARED_CAPABILITIES
    assert 1100 in IBKR_ERROR_RULES
    assert IBKRConnectivityState.LOST.value == "LOST"
    assert IBKRErrorCategory.CONNECTIVITY.value == "CONNECTIVITY"
    assert IBKRErrorDisposition.RECONCILE.value == "RECONCILE"
    assert issubclass(IBKRErrorMappingError, ValueError)
    assert IBKRErrorObservation.__name__ == "IBKRErrorObservation"
    assert IBKRErrorRule.__name__ == "IBKRErrorRule"
    assert IBKRReadinessObservation.__name__ == "IBKRReadinessObservation"
    assert IBKRReadinessDecision.__name__ == "IBKRReadinessDecision"
    assert callable(ibkr_error_rule)
    assert callable(ibkr_connectivity_state)
    assert callable(map_ibkr_provider_error)
    assert callable(evaluate_ibkr_readiness)
    assert callable(assert_ibkr_ready_for_economic_write)
    assert callable(build_ibkr_capability_manifest)
    assert callable(validate_ibkr_capability_manifest)
