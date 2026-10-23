"""Unit tests for IBKR provider primitives and identity semantics."""

from collections.abc import Callable

import pytest

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
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)


def test_order_identity_keeps_order_id_and_perm_id_distinct() -> None:
    identity = IBKROrderIdentity(
        client_id=IBKRClientId(7),
        session_order_id=IBKRSessionOrderId(42),
        client_reference=IBKROrderReference("ptk-order-123"),
    )

    assert identity.routing_key == (7, 42)
    assert not identity.has_durable_identity

    bound = identity.bind_permanent_order_id(IBKRPermanentOrderId(9001))

    assert bound.session_order_id == IBKRSessionOrderId(42)
    assert bound.permanent_order_id == IBKRPermanentOrderId(9001)
    assert bound.has_durable_identity
    assert identity.permanent_order_id is None


def test_provider_order_identity_requires_non_zero_perm_id() -> None:
    identity = IBKROrderIdentity(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(12),
        client_reference=IBKROrderReference("ptk-order-12"),
    )

    with pytest.raises(IBKRIdentityError, match="permId"):
        identity.to_provider_identity()

    provider = identity.bind_permanent_order_id(
        IBKRPermanentOrderId(5012)
    ).to_provider_identity()

    assert provider.provider == "ibkr"
    assert provider.client_reference == "ptk-order-12"
    assert provider.external_order_id == "5012"


def test_perm_id_cannot_be_rebound_to_another_value() -> None:
    identity = IBKROrderIdentity(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(12),
        client_reference=IBKROrderReference("ptk-order-12"),
        permanent_order_id=IBKRPermanentOrderId(5012),
    )

    assert identity.bind_permanent_order_id(IBKRPermanentOrderId(5012)) is identity

    with pytest.raises(IBKRIdentityError, match="rebound"):
        identity.bind_permanent_order_id(IBKRPermanentOrderId(5013))


@pytest.mark.parametrize(
    ("factory", "invalid"),
    [
        (IBKRClientId, -1),
        (IBKRSessionOrderId, -1),
        (IBKRPermanentOrderId, 0),
        (IBKRContractId, 0),
    ],
)
def test_numeric_identity_bounds_are_enforced(
    factory: Callable[[int], object],
    invalid: int,
) -> None:
    with pytest.raises(IBKRIdentityError):
        factory(invalid)


@pytest.mark.parametrize(
    "factory",
    [IBKRClientId, IBKRSessionOrderId, IBKRPermanentOrderId, IBKRContractId],
)
def test_bool_is_not_accepted_as_provider_integer(
    factory: Callable[[int], object],
) -> None:
    with pytest.raises(IBKRIdentityError):
        factory(True)


def test_order_reference_is_trimmed_and_non_empty() -> None:
    assert IBKROrderReference("  ptk-abc  ").value == "ptk-abc"

    with pytest.raises(IBKRIdentityError):
        IBKROrderReference("   ")


def test_execution_identity_maps_exec_id_to_provider_fill_identity() -> None:
    identity = IBKRExecutionIdentity(
        execution_id=IBKRExecutionId("0001.0002.0003.01"),
        permanent_order_id=IBKRPermanentOrderId(500),
        session_order_id=IBKRSessionOrderId(10),
        client_id=IBKRClientId(2),
        order_reference=IBKROrderReference("ptk-500"),
    )

    provider = identity.to_provider_identity()

    assert provider.provider == "ibkr"
    assert provider.external_fill_id == "0001.0002.0003.01"


def test_execution_correction_is_explicit_not_inferred_as_new_fill() -> None:
    previous = IBKRExecutionId("0001.0002.0003.01")
    corrected = IBKRExecutionId("0001.0002.0003.02")
    unrelated = IBKRExecutionId("0001.9999.0003.02")

    assert corrected.can_be_correction_of(previous)
    assert not unrelated.can_be_correction_of(previous)

    correction = IBKRExecutionCorrection(previous=previous, corrected=corrected)

    assert correction.family_id == "0001.0002.0003"

    with pytest.raises(IBKRIdentityError):
        IBKRExecutionCorrection(previous=previous, corrected=unrelated)


def test_contract_identity_maps_con_id_without_making_it_canonical() -> None:
    identity = IBKRContractIdentity(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
    )

    provider = identity.to_provider_identity()

    assert provider.provider == "ibkr"
    assert provider.external_id == "265598"
    assert provider.external_symbol == "AAPL"


def test_connection_identity_is_client_scoped() -> None:
    identity = IBKRConnectionIdentity(client_id=IBKRClientId(17))

    assert identity.client_id.value == 17
