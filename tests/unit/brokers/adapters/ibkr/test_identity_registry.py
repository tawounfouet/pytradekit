"""Unit tests for the IBKR order identity registry."""

import pytest

from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRIdentityError,
    IBKROrderIdentity,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)


def _identity(
    *,
    client_id: int = 1,
    order_id: int = 10,
    order_ref: str = "ptk-10",
    perm_id: int | None = None,
) -> IBKROrderIdentity:
    return IBKROrderIdentity(
        client_id=IBKRClientId(client_id),
        session_order_id=IBKRSessionOrderId(order_id),
        client_reference=IBKROrderReference(order_ref),
        permanent_order_id=(
            IBKRPermanentOrderId(perm_id) if perm_id is not None else None
        ),
    )


def test_registry_can_bind_perm_id_after_initial_order_observation() -> None:
    registry = IBKROrderIdentityRegistry()
    pending = registry.register(_identity())

    assert not pending.has_durable_identity

    bound = registry.bind_permanent_order_id(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(10),
        permanent_order_id=IBKRPermanentOrderId(700),
    )

    assert bound.permanent_order_id == IBKRPermanentOrderId(700)
    assert registry.find_by_permanent_order_id(IBKRPermanentOrderId(700)) == bound
    assert registry.find_by_reference(IBKROrderReference("ptk-10")) == bound
    assert len(registry) == 1


def test_same_perm_id_may_be_observed_under_new_session_routing_key() -> None:
    registry = IBKROrderIdentityRegistry()
    first = registry.register(_identity(client_id=1, order_id=10, perm_id=700))
    rebound = registry.register(_identity(client_id=2, order_id=99, perm_id=700))

    assert first.routing_key != rebound.routing_key
    assert registry.find_by_permanent_order_id(IBKRPermanentOrderId(700)) == rebound
    assert len(registry) == 2


def test_registry_rejects_same_order_ref_with_conflicting_perm_id() -> None:
    registry = IBKROrderIdentityRegistry()
    registry.register(_identity(perm_id=700))

    with pytest.raises(IBKRIdentityError, match="orderRef"):
        registry.register(_identity(client_id=2, order_id=11, perm_id=701))


def test_registry_rejects_perm_id_with_conflicting_order_ref() -> None:
    registry = IBKROrderIdentityRegistry()
    registry.register(_identity(order_ref="ptk-a", perm_id=700))

    with pytest.raises(IBKRIdentityError, match="permId"):
        registry.register(
            _identity(client_id=2, order_id=11, order_ref="ptk-b", perm_id=700)
        )


def test_registry_rejects_conflicting_session_observation() -> None:
    registry = IBKROrderIdentityRegistry()
    registry.register(_identity(order_ref="ptk-a"))

    with pytest.raises(IBKRIdentityError, match="routing identity"):
        registry.register(_identity(order_ref="ptk-b"))


def test_registry_requires_routing_identity_before_perm_binding() -> None:
    registry = IBKROrderIdentityRegistry()

    with pytest.raises(IBKRIdentityError, match="before"):
        registry.bind_permanent_order_id(
            client_id=IBKRClientId(1),
            session_order_id=IBKRSessionOrderId(10),
            permanent_order_id=IBKRPermanentOrderId(700),
        )
