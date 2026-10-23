"""LOT-05.1 qualification for IBKR provider primitives and identity model."""

from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRContractId,
    IBKRContractIdentity,
    IBKRExecutionCorrection,
    IBKRExecutionId,
    IBKRExecutionIdentity,
    IBKROrderIdentity,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)


def test_lot05_01_preserves_order_identity_layers() -> None:
    pending = IBKROrderIdentity(
        client_id=IBKRClientId(3),
        session_order_id=IBKRSessionOrderId(101),
        client_reference=IBKROrderReference("ptk-101"),
    )

    assert pending.session_order_id.value == 101
    assert pending.permanent_order_id is None

    bound = pending.bind_permanent_order_id(IBKRPermanentOrderId(900101))
    provider = bound.to_provider_identity()

    assert provider.client_reference == "ptk-101"
    assert provider.external_order_id == "900101"


def test_lot05_01_preserves_execution_and_contract_identity_layers() -> None:
    execution = IBKRExecutionIdentity(
        execution_id=IBKRExecutionId("a.b.c.01"),
    ).to_provider_identity()
    contract = IBKRContractIdentity(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    ).to_provider_identity()

    assert execution.external_fill_id == "a.b.c.01"
    assert contract.external_id == "265598"


def test_lot05_01_models_execution_correction_without_creating_fill_semantics() -> None:
    correction = IBKRExecutionCorrection(
        previous=IBKRExecutionId("a.b.c.01"),
        corrected=IBKRExecutionId("a.b.c.02"),
    )

    assert correction.family_id == "a.b.c"
