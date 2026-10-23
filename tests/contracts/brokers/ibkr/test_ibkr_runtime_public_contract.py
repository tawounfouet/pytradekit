"""Public contract for IBKR LOT-06.1 PAPER connection runtime."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ASYNC_PACKAGE_NAME,
    IBKR_ASYNC_VERSION_TARGET,
    IBKR_PAPER_RUNTIME_VERSION,
    IBAsyncPaperTransport,
    IBKRPaperConnectionRuntime,
    IBKRPaperRuntimeProfile,
    IBKRRuntimeConfigurationError,
    IBKRRuntimeDependencyError,
    IBKRTransportConnectionEvidence,
    IBKRTransportPort,
    build_ibkr_paper_connection_runtime,
)


def test_ibkr_lot06_1_public_surface_is_exported() -> None:
    assert IBKR_ASYNC_PACKAGE_NAME == "ib_async"
    assert IBKR_ASYNC_VERSION_TARGET == "2.1.0"
    assert IBKR_PAPER_RUNTIME_VERSION == "0.8.0b2-lot06.1"
    assert IBAsyncPaperTransport.__name__ == "IBAsyncPaperTransport"
    assert IBKRPaperConnectionRuntime.__name__ == "IBKRPaperConnectionRuntime"
    assert IBKRPaperRuntimeProfile.__name__ == "IBKRPaperRuntimeProfile"
    assert issubclass(IBKRRuntimeConfigurationError, ValueError)
    assert issubclass(IBKRRuntimeDependencyError, RuntimeError)
    assert IBKRTransportConnectionEvidence.__name__ == (
        "IBKRTransportConnectionEvidence"
    )
    assert IBKRTransportPort.__name__ == "IBKRTransportPort"
    assert callable(build_ibkr_paper_connection_runtime)
