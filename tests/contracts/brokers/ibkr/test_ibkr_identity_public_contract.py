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
    client_id = IBKRClientId(0)
    session_order_id = IBKRSessionOrderId(1)
    permanent_order_id = IBKRPermanentOrderId(1)
    reference = IBKROrderReference("ptk-1")
    execution_id = IBKRExecutionId("x.01")
    contract_id = IBKRContractId(1)

    assert IBKRConnectionIdentity(client_id=client_id).client_id == client_id
    assert IBKROrderIdentity(
        client_id=client_id,
        session_order_id=session_order_id,
        client_reference=reference,
        permanent_order_id=permanent_order_id,
    ).has_durable_identity
    assert IBKRExecutionIdentity(execution_id=execution_id).execution_id == execution_id
    assert IBKRExecutionCorrection(
        previous=IBKRExecutionId("x.01"),
        corrected=IBKRExecutionId("x.02"),
    ).family_id == "x"
    assert IBKRContractIdentity(
        contract_id=contract_id,
        symbol="AAPL",
    ).contract_id == contract_id
    assert len(IBKROrderIdentityRegistry()) == 0
    assert issubclass(IBKRIdentityError, ValueError)
