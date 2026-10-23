"""Public contract for IBKR LOT-06.4 order session runtime."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ORDER_SESSION_VERSION,
    IBKRCallbackCorrelationRouter,
    IBKRCorrelatedOpenOrder,
    IBKRCorrelatedOrderError,
    IBKRCorrelatedOrderStatus,
    IBKROrderCorrelationRegistry,
    IBKROrderSessionError,
    IBKROrderSessionReservation,
    IBKROrderSessionRuntime,
    IBKROrderSessionSequencer,
    build_ibkr_order_session_runtime,
)


def test_ibkr_lot06_4_public_surface_is_exported() -> None:
    assert IBKR_ORDER_SESSION_VERSION == "0.8.0b5-lot06.4"
    assert IBKRCallbackCorrelationRouter.__name__ == (
        "IBKRCallbackCorrelationRouter"
    )
    assert IBKRCorrelatedOpenOrder.__name__ == "IBKRCorrelatedOpenOrder"
    assert IBKRCorrelatedOrderError.__name__ == "IBKRCorrelatedOrderError"
    assert IBKRCorrelatedOrderStatus.__name__ == "IBKRCorrelatedOrderStatus"
    assert IBKROrderCorrelationRegistry.__name__ == (
        "IBKROrderCorrelationRegistry"
    )
    assert issubclass(IBKROrderSessionError, ValueError)
    assert IBKROrderSessionReservation.__name__ == (
        "IBKROrderSessionReservation"
    )
    assert IBKROrderSessionRuntime.__name__ == "IBKROrderSessionRuntime"
    assert IBKROrderSessionSequencer.__name__ == "IBKROrderSessionSequencer"
    assert callable(build_ibkr_order_session_runtime)
