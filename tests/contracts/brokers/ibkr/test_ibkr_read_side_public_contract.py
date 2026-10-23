"""Public contract for IBKR LOT-06.2 read-side reconciliation."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_READ_SIDE_VERSION,
    IBKR_STARTUP_RECONCILIATION_VERSION,
    IBKRAccountRestrictionsProvider,
    IBKRBrokerSnapshotPort,
    IBKRInstrumentResolver,
    IBKROrderIdentityResolver,
    IBKRReadSideCaptureStats,
    IBKRReadSideClient,
    IBKRReadSideError,
    IBKRStartupReconciliationGate,
    IBKRStartupReconciliationWorkflow,
)


def test_ibkr_lot06_2_public_surface_is_exported() -> None:
    assert IBKR_READ_SIDE_VERSION == "0.8.0b3-lot06.2"
    assert IBKR_STARTUP_RECONCILIATION_VERSION == "0.8.0b3-lot06.2"
    assert IBKRAccountRestrictionsProvider.__name__ == (
        "IBKRAccountRestrictionsProvider"
    )
    assert IBKRBrokerSnapshotPort.__name__ == "IBKRBrokerSnapshotPort"
    assert IBKRInstrumentResolver.__name__ == "IBKRInstrumentResolver"
    assert IBKROrderIdentityResolver.__name__ == "IBKROrderIdentityResolver"
    assert IBKRReadSideCaptureStats.__name__ == "IBKRReadSideCaptureStats"
    assert IBKRReadSideClient.__name__ == "IBKRReadSideClient"
    assert issubclass(IBKRReadSideError, ValueError)
    assert IBKRStartupReconciliationGate.__name__ == (
        "IBKRStartupReconciliationGate"
    )
    assert IBKRStartupReconciliationWorkflow.__name__ == (
        "IBKRStartupReconciliationWorkflow"
    )
