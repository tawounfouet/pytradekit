"""Public contract for IBKR provider-specific identity primitives."""

from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRConnectionIdentity,
    IBKRContractId,
    IBKRContractIdentity,
    IBKRExecutionCorrection,
    IBKRExecutionId,
    IBKRExecutionIdentity,
    IBKRIdentityError,
    IBKROrderIdentity,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)


def test_ibkr_identity_surface_is_importable() -> None:
    assert IBKRClientId(0).value == 0
    assert IBKRSessionOrderId(1).value == 1
    assert IBKRPermanentOrderId(1).value == 1
    assert IBKROrderReference("ptk-1").value == "ptk-1"
    assert IBKRExecutionId("x.01").value == "x.01"
    assert IBKRContractId(1).value == 1
    assert IBKRConnectionIdentity(client_id=IBKRClientId(0))
    assert IBKROrderIdentity
    assert IBKRExecutionIdentity
    assert IBKRExecutionCorrection
    assert IBKRContractIdentity
    assert IBKROrderIdentityRegistry
    assert issubclass(IBKRIdentityError, ValueError)
