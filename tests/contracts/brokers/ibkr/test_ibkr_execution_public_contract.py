"""Public contract for IBKR LOT-06.5 economic-write execution."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ECONOMIC_WRITE_VERSION,
    IBKREconomicWriteAdmission,
    IBKREconomicWriteAttempt,
    IBKRExecutionAdapter,
    IBKRExecutionAdapterError,
    IBKRExecutionInstrumentBinding,
    IBKRExecutionInstrumentResolver,
    IBKRSDKPlacement,
    IBKRSDKPlacementFactory,
    StaticIBKRExecutionInstrumentResolver,
    build_ibkr_execution_adapter,
)


def test_ibkr_lot06_5_public_surface_is_exported() -> None:
    assert IBKR_ECONOMIC_WRITE_VERSION == "0.8.0b6-lot06.5"
    assert IBKREconomicWriteAdmission.__name__ == "IBKREconomicWriteAdmission"
    assert IBKREconomicWriteAttempt.__name__ == "IBKREconomicWriteAttempt"
    assert IBKRExecutionAdapter.__name__ == "IBKRExecutionAdapter"
    assert issubclass(IBKRExecutionAdapterError, ValueError)
    assert IBKRExecutionInstrumentBinding.__name__ == (
        "IBKRExecutionInstrumentBinding"
    )
    assert IBKRExecutionInstrumentResolver.__name__ == (
        "IBKRExecutionInstrumentResolver"
    )
    assert IBKRSDKPlacement.__name__ == "IBKRSDKPlacement"
    assert IBKRSDKPlacementFactory.__name__ == "IBKRSDKPlacementFactory"
    assert StaticIBKRExecutionInstrumentResolver.__name__ == (
        "StaticIBKRExecutionInstrumentResolver"
    )
    assert callable(build_ibkr_execution_adapter)
