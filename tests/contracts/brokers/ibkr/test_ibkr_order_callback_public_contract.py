"""Public contract for IBKR SDK-free order callback normalization."""

from pytradekit.brokers.adapters.ibkr import (
    IBKROpenOrderObservation,
    IBKROrderCallbackError,
    IBKROrderErrorObservation,
    IBKROrderStateDisposition,
    IBKROrderStateRule,
    IBKROrderStatus,
    IBKROrderStatusObservation,
    ibkr_order_status_rule,
    map_ibkr_order_error_report,
    map_ibkr_order_status_report,
    map_ibkr_order_status_snapshot,
    register_ibkr_open_order_observation,
)


def test_ibkr_order_callback_surface_is_public() -> None:
    assert IBKROrderStatus.PENDING_SUBMIT.value == "PendingSubmit"
    assert IBKROrderStatus.PRE_SUBMITTED.value == "PreSubmitted"
    assert IBKROrderStatus.SUBMITTED.value == "Submitted"
    assert IBKROrderStatus.PENDING_CANCEL.value == "PendingCancel"
    assert IBKROrderStatus.API_CANCELLED.value == "ApiCancelled"
    assert IBKROrderStatus.CANCELLED.value == "Cancelled"
    assert IBKROrderStatus.FILLED.value == "Filled"
    assert IBKROrderStatus.INACTIVE.value == "Inactive"
    assert IBKROrderStateDisposition.RECONCILE.value == "reconcile"
    assert IBKROrderStateRule.__name__ == "IBKROrderStateRule"
    assert IBKROpenOrderObservation.__name__ == "IBKROpenOrderObservation"
    assert IBKROrderStatusObservation.__name__ == "IBKROrderStatusObservation"
    assert IBKROrderErrorObservation.__name__ == "IBKROrderErrorObservation"
    assert issubclass(IBKROrderCallbackError, ValueError)
    assert callable(ibkr_order_status_rule)
    assert callable(register_ibkr_open_order_observation)
    assert callable(map_ibkr_order_status_snapshot)
    assert callable(map_ibkr_order_status_report)
    assert callable(map_ibkr_order_error_report)
